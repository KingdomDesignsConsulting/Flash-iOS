/*
 * chat.m — Interactive TUI chat client for Flash-MoE inference server
 *
 * Thin HTTP/SSE client with session persistence.
 * Conversations saved to ~/.flash-moe/sessions/<session_id>.jsonl
 * Resume with: ./chat --resume <session_id>
 *
 * Build:  make chat
 * Run:    ./chat [--port 8000] [--show-think] [--resume <id>]
 */

#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <getopt.h>
#include <dirent.h>
#include <errno.h>
#include <signal.h>
#include <poll.h>
#include <fcntl.h>
#include <sys/file.h>
#include "linenoise.h"

#define MAX_INPUT_LINE 4096
#define MAX_RESPONSE (1024 * 1024)
#define SESSIONS_DIR_BASE ".flash-moe/sessions"

static double now_ms(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec * 1000.0 + tv.tv_usec / 1000.0;
}

// ============================================================================
// Session persistence
// ============================================================================

static char g_sessions_dir[1024];

static void init_sessions_dir(void) {
    const char *override=getenv("FLASH_CHAT_STATE_DIR");
    if(override && *override) {
        if(strlen(override)>=sizeof(g_sessions_dir)) {fprintf(stderr,"State directory too long.\n");exit(1);}
        strcpy(g_sessions_dir,override);
        if(![[NSFileManager defaultManager] createDirectoryAtPath:@(override) withIntermediateDirectories:YES attributes:nil error:NULL])exit(1);
        return;
    }
    const char *home = getenv("HOME");
    if (!home) home = "/tmp";
    snprintf(g_sessions_dir, sizeof(g_sessions_dir), "%s/%s", home, SESSIONS_DIR_BASE);
    mkdir(g_sessions_dir, 0755);
    // Also create parent
    char parent[1024];
    snprintf(parent, sizeof(parent), "%s/.flash-moe", home);
    mkdir(parent, 0755);
    mkdir(g_sessions_dir, 0755);
}

static int session_id_valid(const char *session_id) {
    if (!session_id) return 0;
    size_t n = strlen(session_id);
    if (n == 0 || n > 64) return 0;
    for (size_t i = 0; i < n; i++) {
        unsigned char c = (unsigned char)session_id[i];
        if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
              (c >= '0' && c <= '9') || c == '_' || c == '-'))
            return 0;
    }
    return 1;
}

static int session_path(const char *session_id, char *path, size_t pathsize) {
    if (!session_id_valid(session_id)) return 0;
    int n = snprintf(path, pathsize, "%s/%s.jsonl", g_sessions_dir, session_id);
    return n >= 0 && (size_t)n < pathsize;
}

// Commit a completed logical exchange with one atomic replacement. A failed
// transport never reaches this function. No orphan user turn can be appended.
static NSMutableArray *read_transcript(const char *session_id);
static int session_commit_exchange_unlocked(const char *sid, NSArray *expected, NSDictionary *turn, const char *reply) {
    NSMutableArray *history=read_transcript(sid);
    if (!history || ![history isEqual:expected] || !reply || !*reply) return 0;
    [history addObject:turn];
    [history addObject:@{@"role":@"assistant",@"content":@(reply)}];
    NSMutableData *data=[NSMutableData data];
    for (NSDictionary *m in history) {
        NSData *line=[NSJSONSerialization dataWithJSONObject:m options:0 error:NULL];
        if (!line) return 0;
        [data appendData:line]; [data appendBytes:"\n" length:1];
    }
    if(data.length>16*MAX_RESPONSE) return 0;
    char path[1024],tmp[1100];
    if(!session_path(sid,path,sizeof(path))) return 0;
    snprintf(tmp,sizeof(tmp),"%s.tmp.XXXXXX",path);
    int fd=mkstemp(tmp); if(fd<0)return 0;
    const char *bytes=data.bytes;size_t done=0;
    while(done<data.length) {ssize_t n=write(fd,bytes+done,data.length-done);if(n<0&&errno==EINTR)continue;if(n<=0)break;done+=(size_t)n;}
    int ok=done==data.length && fsync(fd)==0;
    if(close(fd)!=0)ok=0;
    if(ok && rename(tmp,path)!=0)ok=0;
    if(!ok)unlink(tmp);
    return ok;
}

// Serialize concurrent writers and reject a stale generation's history anchor.
static int session_commit_exchange(const char *sid, NSArray *expected, NSDictionary *turn, const char *reply) {
    char path[1024],lock_path[1100];if(!session_path(sid,path,sizeof(path)))return 0;
    snprintf(lock_path,sizeof(lock_path),"%s.lock",path);
    int fd=open(lock_path,O_CREAT|O_RDWR,0600);if(fd<0)return 0;
    int ok=0;if(flock(fd,LOCK_EX)==0) {
        ok=session_commit_exchange_unlocked(sid,expected,turn,reply);
        flock(fd,LOCK_UN);
    }
    close(fd);return ok;
}

// Load session history and replay to screen
static int session_load(const char *session_id) {
    NSMutableArray *turns=read_transcript(session_id);
    if(!turns)return 0;
    printf("[resuming session %s]\n",session_id);
    for(NSDictionary *m in turns)printf("%s: %s\n",[m[@"role"] UTF8String],[m[@"content"] UTF8String]);
    return (int)turns.count;
}

// List recent sessions
static void session_list(void) {
    DIR *dir = opendir(g_sessions_dir);
    if (!dir) { printf("No sessions found.\n\n"); return; }

    printf("Recent sessions:\n");
    struct dirent *entry;
    int count = 0;
    while ((entry = readdir(dir))) {
        if (entry->d_name[0] == '.') continue;
        char *dot = strrchr(entry->d_name, '.');
        if (!dot || strcmp(dot, ".jsonl") != 0) continue;
        *dot = 0; // strip .jsonl

        char path[1024];
        snprintf(path, sizeof(path), "%s/%s.jsonl", g_sessions_dir, entry->d_name);
        struct stat st;
        stat(path, &st);

        // Count lines (turns)
        FILE *f = fopen(path, "r");
        int lines = 0;
        if (f) {
            char buf[1024];
            while (fgets(buf, sizeof(buf), f)) lines++;
            fclose(f);
        }

        printf("  %s  (%d turns)\n", entry->d_name, lines);
        count++;
    }
    closedir(dir);
    if (count == 0) printf("  (none)\n");
    printf("\n");
}

// ============================================================================
// HTTP / SSE
// ============================================================================

static void generate_session_id(char *buf, size_t bufsize) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    snprintf(buf, bufsize, "chat-%d-%ld%06d",
             (int)getpid(), (long)tv.tv_sec, (int)tv.tv_usec);
}

static int write_all(int fd, const void *buf, size_t len) {
    const uint8_t *p = (const uint8_t *)buf;
    size_t off = 0;
    while (off < len) {
        ssize_t n = write(fd, p + off, len - off);
        if (n > 0) {
            off += (size_t)n;
            continue;
        }
        if (n < 0 && errno == EINTR) continue;
        return -1;
    }
    return 0;
}


static NSMutableArray *read_transcript(const char *session_id) {
    char path[1024];
    if (!session_path(session_id, path, sizeof(path))) return nil;
    if (access(path, F_OK) != 0) return errno == ENOENT ? [NSMutableArray array] : nil;
    NSDictionary *attrs=[[NSFileManager defaultManager] attributesOfItemAtPath:@(path) error:NULL];
    if([attrs[NSFileSize] unsignedLongLongValue]>16*MAX_RESPONSE)return nil;
    NSError *error = nil;
    NSString *raw = [NSString stringWithContentsOfFile:@(path)
                                             encoding:NSUTF8StringEncoding error:&error];
    if (!raw) return nil;
    NSMutableArray *turns = [NSMutableArray array];
    for (NSString *line in [raw componentsSeparatedByString:@"\n"]) {
        if (!line.length) continue;
        id item = [NSJSONSerialization JSONObjectWithData:
                  [line dataUsingEncoding:NSUTF8StringEncoding] options:0 error:&error];
        if (![item isKindOfClass:[NSDictionary class]] || [item count]!=2 ||
            ![@[@"user", @"assistant"] containsObject:item[@"role"]] ||
            ![item[@"content"] isKindOfClass:[NSString class]]) {
            fprintf(stderr, "[chat] Corrupt transcript; refusing partial replay.\n");
            return nil;
        }
        [turns addObject:@{@"role":item[@"role"], @"content":item[@"content"]}];
    }
    if(turns.count%2) {fprintf(stderr,"[chat] Incomplete transcript exchange; refusing replay.\n");return nil;}
    for(NSUInteger i=0;i<turns.count;i++)if(![turns[i][@"role"] isEqual:(i%2?@"assistant":@"user")])return nil;
    return turns;
}

// When create=1 send full history. Otherwise send only the new turn.
static int send_chat_request(int port, NSArray *messages, int max_tokens,
                             const char *session_id, int create) {
    if (!session_id_valid(session_id)) return -1;
    NSDictionary *payload = @{@"model":@"qwen3.5", @"messages":messages,
        @"max_tokens":@(max_tokens), @"stream":@YES,
        @"session_id":@(session_id), @"flash_session_create":@(create != 0)};
    NSData *data = [NSJSONSerialization dataWithJSONObject:payload options:0 error:NULL];
    if (!data) return -1;
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) { perror("socket"); return -1; }
    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    addr.sin_addr.s_addr = inet_addr("127.0.0.1");
    int flags=fcntl(sock,F_GETFL,0);fcntl(sock,F_SETFL,flags|O_NONBLOCK);
    int connected=connect(sock,(struct sockaddr *)&addr,sizeof(addr));
    if(connected<0 && errno==EINPROGRESS) {struct pollfd p={sock,POLLOUT,0};if(poll(&p,1,5000)>0){int err=0;socklen_t size=sizeof(err);if(getsockopt(sock,SOL_SOCKET,SO_ERROR,&err,&size)==0 && err==0)connected=0;}}
    fcntl(sock,F_SETFL,flags);
    struct timeval timeout={120,0};
    const char *timeout_env=getenv("FLASH_CHAT_TIMEOUT_MS");
    if(timeout_env){long ms=strtol(timeout_env,NULL,10);if(ms>=50 && ms<=600000){timeout.tv_sec=ms/1000;timeout.tv_usec=(ms%1000)*1000;}}
    setsockopt(sock,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
    setsockopt(sock,SOL_SOCKET,SO_SNDTIMEO,&timeout,sizeof(timeout));
    int no_sigpipe=1;setsockopt(sock,SOL_SOCKET,SO_NOSIGPIPE,&no_sigpipe,sizeof(no_sigpipe));
    if (connected < 0) {
        fprintf(stderr, "[chat] Cannot connect on port %d.\n", port);
        close(sock); return -1;
    }
    char header[512];
    int n = snprintf(header, sizeof(header),
        "POST /v1/chat/completions HTTP/1.1\r\n"
        "Host: localhost:%d\r\nContent-Type: application/json\r\n"
        "Content-Length: %lu\r\nConnection: close\r\n\r\n",
        port, (unsigned long)data.length);
    if (n <= 0 || n >= (int)sizeof(header) ||
        write_all(sock, header, n) < 0 ||
        write_all(sock, data.bytes, data.length) < 0) {
        close(sock); return -1;
    }
    return sock;
}

// ============================================================================
// Streaming markdown renderer — stateful ANSI escape code emitter
// ============================================================================
// Handles: **bold**, *italic*, `inline code`, ```code blocks```, # headers
// State persists across token boundaries (e.g. "**" in one token, text in next)

#define ANSI_RESET   "\033[0m"
#define ANSI_BOLD    "\033[1m"
#define ANSI_ITALIC  "\033[3m"
#define ANSI_CODE    "\033[36m"      // cyan for inline code
#define ANSI_CODEBLK "\033[48;5;236m\033[38;5;252m"  // dark bg + light fg
#define ANSI_CODEBLK_LINE "\033[48;5;236m\033[K"     // extend bg to end of line
#define ANSI_HEADER  "\033[1;34m"    // bold blue for headers
#define ANSI_DIM     "\033[2m"

typedef struct {
    int bold;        // inside **...**
    int italic;      // inside *...*
    int code_inline; // inside `...`
    int code_block;  // inside ```...```
    int skip_lang;   // eating language tag after opening ```
    int line_start;  // at start of a new line
    char pending[8]; // buffered chars for lookahead (e.g., partial "**")
    int pending_len;
} MdState;

static MdState g_md = {.line_start = 1};

static void md_reset(void) {
    memset(&g_md, 0, sizeof(g_md));
    g_md.line_start = 1;
}

static void md_print(const char *text) {
    for (int i = 0; text[i]; i++) {
        char c = text[i];

        // Skip language tag after opening ``` (may span tokens)
        if (g_md.skip_lang) {
            if (c == '\n') {
                g_md.skip_lang = 0;
                printf(ANSI_CODEBLK ANSI_CODEBLK_LINE "\n");
            }
            // else: eat the character (language tag)
            continue;
        }

        // Code block toggle: ```
        if (c == '`' && text[i+1] == '`' && text[i+2] == '`') {
            if (g_md.code_block) {
                printf(ANSI_RESET "\n");
                g_md.code_block = 0;
            } else {
                g_md.code_block = 1;
                g_md.skip_lang = 1;  // eat language tag until newline
            }
            i += 2;
            continue;
        }

        // Inside code block: print with full-width background
        if (g_md.code_block) {
            printf(ANSI_CODEBLK);
            if (c == '\n') {
                printf(ANSI_CODEBLK_LINE "\n");
            } else {
                putchar(c);
            }
            continue;
        }

        // Inline code toggle: `
        if (c == '`') {
            if (g_md.code_inline) {
                printf(ANSI_RESET);
                g_md.code_inline = 0;
            } else {
                printf(ANSI_CODE);
                g_md.code_inline = 1;
            }
            continue;
        }

        // Inside inline code: print verbatim
        if (g_md.code_inline) {
            putchar(c);
            continue;
        }

        // Headers at line start: # ## ### — hide markers, show text bold blue
        if (g_md.line_start && c == '#') {
            while (text[i] == '#') i++;  // skip all #
            while (text[i] == ' ') i++;  // skip space after #
            printf(ANSI_HEADER);
            while (text[i] && text[i] != '\n') { putchar(text[i]); i++; }
            printf(ANSI_RESET);
            if (text[i] == '\n') { putchar('\n'); g_md.line_start = 1; }
            continue;
        }

        // Bullet lists: - or * at line start (possibly indented with spaces)
        // Count leading spaces for indent level, then check for bullet marker
        if (g_md.line_start && (c == '-' || c == '*' || c == ' ')) {
            // Peek ahead: count indent, find marker
            int indent = 0;
            int peek = i;
            while (text[peek] == ' ' || text[peek] == '\t') { indent++; peek++; }
            char marker = text[peek];
            if ((marker == '-' || marker == '*') && marker != '\0') {
                char after = text[peek + 1];
                // Bullet: marker followed by space, end of token, or tab
                // For *, must not be ** (bold)
                if (marker == '-' && (after == ' ' || after == '\0')) {
                    int depth = indent / 2;
                    for (int d = 0; d < depth + 1; d++) printf("  ");
                    printf("\033[33m•\033[0m ");
                    i = peek + 1;
                    while (text[i] == ' ' || text[i] == '\t') i++;
                    i--; // loop will i++
                    g_md.line_start = 0;
                    continue;
                }
                if (marker == '*' && after != '*' && (after == ' ' || after == '\0' || after == '\t')) {
                    int depth = indent / 2;
                    for (int d = 0; d < depth + 1; d++) printf("  ");
                    printf("\033[33m•\033[0m ");
                    i = peek + 1;
                    while (text[i] == ' ' || text[i] == '\t') i++;
                    i--;
                    g_md.line_start = 0;
                    continue;
                }
            }
            // Not a bullet — fall through to normal handling
        }

        // Numbered lists at line start: 1. item → colored number
        if (g_md.line_start && c >= '0' && c <= '9') {
            int num_start = i;
            while (text[i] >= '0' && text[i] <= '9') i++;
            if (text[i] == '.' && text[i+1] == ' ') {
                printf("  \033[33m");  // yellow
                for (int j = num_start; j <= i; j++) putchar(text[j]);
                printf("\033[0m");
                i++; // skip space
                g_md.line_start = 0;
                continue;
            }
            // Not a list, rewind and print normally
            i = num_start;
            c = text[i];
        }

        // Bold: **
        if (c == '*' && text[i+1] == '*') {
            if (g_md.bold) {
                printf(ANSI_RESET);
                g_md.bold = 0;
            } else {
                printf(ANSI_BOLD);
                g_md.bold = 1;
            }
            i++;
            continue;
        }

        // Italic: single * (but not **)
        if (c == '*' && text[i+1] != '*') {
            if (g_md.italic) {
                printf(ANSI_RESET);
                g_md.italic = 0;
            } else {
                printf(ANSI_ITALIC);
                g_md.italic = 1;
            }
            continue;
        }

        // Track line starts
        if (c == '\n') {
            g_md.line_start = 1;
        } else {
            g_md.line_start = 0;
        }

        putchar(c);
    }
}

// Stream SSE response, accumulate text, return malloc'd response string
#include "chat_transport.inc"

// ============================================================================
// Main
// ============================================================================

int main(int argc, char **argv) {
    struct sigaction action={0};action.sa_handler=chat_cancel;sigaction(SIGINT,&action,NULL);
    int port = 8000;
    int max_tokens = 8192;
    int show_thinking = 0;
    const char *resume_id = NULL;

    static struct option long_options[] = {
        {"port",        required_argument, 0, 'p'},
        {"max-tokens",  required_argument, 0, 't'},
        {"show-think",  no_argument,       0, 's'},
        {"resume",      required_argument, 0, 'r'},
        {"sessions",    no_argument,       0, 'l'},
        {"help",        no_argument,       0, 'h'},
        {0, 0, 0, 0}
    };

    init_sessions_dir();

    int c;
    while ((c = getopt_long(argc, argv, "p:t:sr:lh", long_options, NULL)) != -1) {
        switch (c) {
            case 'p': port = atoi(optarg); break;
            case 't': max_tokens = atoi(optarg); break;
            case 's': show_thinking = 1; break;
            case 'r': resume_id = optarg; break;
            case 'l': session_list(); return 0;
            case 'h':
                printf("Usage: %s [options]\n", argv[0]);
                printf("  --port N         Server port (default: 8000)\n");
                printf("  --max-tokens N   Max response tokens (default: 8192)\n");
                printf("  --show-think     Show <think> blocks (dimmed)\n");
                printf("  --resume ID      Resume a previous session\n");
                printf("  --sessions       List saved sessions\n");
                printf("  --help           This message\n");
                return 0;
            default: return 1;
        }
    }

    char session_id[65];
    if (resume_id) {
        if (!session_id_valid(resume_id)) {
            fprintf(stderr, "Invalid session ID: use 1-64 letters, digits, '_' or '-'.\n");
            return 1;
        }
        strncpy(session_id, resume_id, sizeof(session_id) - 1);
        session_id[sizeof(session_id) - 1] = 0;
    } else {
        generate_session_id(session_id, sizeof(session_id));
    }

    printf("==================================================\n");
    printf("  Qwen3.5-397B-A17B Chat (Flash-MoE)\n");
    printf("==================================================\n");
    printf("  Server:  http://localhost:%d\n", port);
    printf("  Session: %s%s\n", session_id, resume_id ? " (resumed)" : "");
    printf("\n  Commands: /quit /exit /clear /sessions\n");
    printf("==================================================\n\n");

    // Health check
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    addr.sin_addr.s_addr = inet_addr("127.0.0.1");
    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        fprintf(stderr, "Server not running on port %d.\n", port);
        fprintf(stderr, "Start it: ./infer --serve %d\n\n", port);
        close(sock);
        return 1;
    }
    close(sock);

    // Resume: load and display previous conversation
    if (resume_id) {
        int turns = session_load(session_id);
        if (turns == 0) {
            printf("No session found with ID: %s\n\n", session_id);
        }
        char saved_path[1024];
        if(!session_path(session_id,saved_path,sizeof(saved_path)) || access(saved_path,F_OK)!=0 || !read_transcript(session_id)) {fprintf(stderr,"Cannot faithfully resume transcript.\n");return 1;}
    }

    printf("Ready to chat.\n\n");

    // Set up linenoise: history, hints
    linenoiseSetMultiLine(1);  // allow multi-line input with arrow keys
    char history_path[1024];
    snprintf(history_path, sizeof(history_path), "%s/history", g_sessions_dir);
    linenoiseHistoryLoad(history_path);
    linenoiseHistorySetMaxLen(500);

    char server_session_id[65];
    generate_session_id(server_session_id, sizeof(server_session_id));
    int server_session_live = 0;
    for (;;) {
        char *line = linenoise("> ");
        if (!line) {
            printf("\n");
            break;
        }

        size_t len = strlen(line);
        if (len == 0) { free(line); continue; }

        // Add to history
        linenoiseHistoryAdd(line);
        linenoiseHistorySave(history_path);

        if(len>=MAX_INPUT_LINE){fprintf(stderr,"Input too long; not truncated.\n");free(line);continue;}
        char input_line[MAX_INPUT_LINE];
        strncpy(input_line, line, MAX_INPUT_LINE - 1);
        input_line[MAX_INPUT_LINE - 1] = 0;
        free(line);

        if (strcmp(input_line, "/quit") == 0 || strcmp(input_line, "/exit") == 0) {
            printf("Goodbye.\n");
            break;
        }
        if (strcmp(input_line, "/clear") == 0) {
            generate_session_id(session_id, sizeof(session_id));
            generate_session_id(server_session_id, sizeof(server_session_id));
            server_session_live = 0;
            printf("[new session: %s]\n\n", session_id);
            continue;
        }
        if (strcmp(input_line, "/sessions") == 0) {
            session_list();
            continue;
        }

        NSMutableArray *history = read_transcript(session_id);
        if (!history) { fprintf(stderr, "[chat] Failed to load transcript; request blocked.\n"); continue; }
        char transcript_path[1024];session_path(session_id,transcript_path,sizeof(transcript_path));
        NSString *pending_path=[@(transcript_path) stringByAppendingString:@".pending.json"];
        NSDictionary *turn = @{@"role":@"user", @"content":@(input_line)};
        if([[NSFileManager defaultManager] fileExistsAtPath:pending_path]) {
            if(strcmp(input_line,"/retry-tool")) {fprintf(stderr,"[chat] Pending tool output: use /retry-tool or /clear; command will not run again.\n");continue;}
            id pending=[NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:pending_path] options:0 error:NULL];
            if(![pending isKindOfClass:[NSDictionary class]] || ![pending[@"role"] isEqual:@"user"] || ![pending[@"content"] isKindOfClass:[NSString class]]) {fprintf(stderr,"Invalid pending tool output.\n");continue;}
            NSUInteger anchor=[pending[@"anchor_count"] unsignedIntegerValue];
            NSDictionary *savedTurn=@{@"role":pending[@"role"],@"content":pending[@"content"]};
            if(![pending[@"anchor_count"] isKindOfClass:[NSNumber class]]){fprintf(stderr,"Unanchored pending output; refusing guessed replay.\n");continue;}
            if(history.count==anchor+2 && [history[anchor] isEqual:savedTurn]) {
                [[NSFileManager defaultManager] removeItemAtPath:pending_path error:NULL];
                fprintf(stderr,"[chat] Tool output already committed; no duplicate submission.\n");continue;
            }
            if(history.count!=anchor){fprintf(stderr,"Pending output/history mismatch; refusing replay.\n");continue;}
            turn=savedTurn;
        }
        [history addObject:turn];
        char *response=perform_turn(port,history,turn,max_tokens,server_session_id,&server_session_live,show_thinking);
        if(!response) {fprintf(stderr,"[chat] Request failed; no local turns saved.\n");continue;}
        if(!session_commit_exchange(session_id,[history subarrayWithRange:NSMakeRange(0,history.count-1)],turn,response)) {
            fprintf(stderr,"[chat] Transcript commit failed; stopping without claiming persistence.\n");free(response);return 1;
        }

        [[NSFileManager defaultManager] removeItemAtPath:pending_path error:NULL];

        // ---- Tool call handling ----
        // Detect <tool_call>{"name":"bash","arguments":{"command":"..."}}
        // Execute the command, feed output back as a continuation
        while (response && strstr(response, "<tool_call>")) {
            char *tc_start = strstr(response, "<tool_call>");
            char *tc_end = strstr(tc_start, "</tool_call>");
            if (!tc_start || !tc_end) break;

            // Extract content between tags
            tc_start += 11;  // skip <tool_call>
            char tc_body[4096] = {0};
            int tc_len = (int)(tc_end - tc_start);
            if (tc_len > 4095) tc_len = 4095;
            memcpy(tc_body, tc_start, tc_len);

            // Parse command — handle multiple formats the model might produce:
            // 1. JSON: {"name":"bash","arguments":{"command":"ls -la"}}
            // 2. XML-ish: <function=bash><arg_key>command</arg_key><arg_value>ls -la</arg_value>
            // 3. Simple: just a command string
            char command[4096] = {0};
            int ci = 0;

            char *cmd_key = strstr(tc_body, "\"command\"");
            if (cmd_key) {
                // JSON format: find value after "command":"
                cmd_key = strchr(cmd_key + 9, '"');
                if (cmd_key) {
                    cmd_key++;
                    for (int i = 0; cmd_key[i] && cmd_key[i] != '"' && ci < 4095; i++) {
                        if (cmd_key[i] == '\\' && cmd_key[i+1]) {
                            i++;
                            switch (cmd_key[i]) {
                                case 'n': command[ci++] = '\n'; break;
                                case '"': command[ci++] = '"'; break;
                                case '\\': command[ci++] = '\\'; break;
                                default: command[ci++] = cmd_key[i]; break;
                            }
                        } else {
                            command[ci++] = cmd_key[i];
                        }
                    }
                }
            }
            // Fallback: look for <arg_value>...</arg_value> (model's XML format)
            if (ci == 0) {
                char *av = strstr(tc_body, "<arg_value>");
                if (av) {
                    av += 11;
                    char *av_end = strstr(av, "</arg_value>");
                    if (!av_end) av_end = strstr(av, "<");
                    if (av_end) {
                        int avlen = (int)(av_end - av);
                        if (avlen > 4095) avlen = 4095;
                        memcpy(command, av, avlen);
                        ci = avlen;
                        // Trim whitespace
                        while (ci > 0 && (command[ci-1] == '\n' || command[ci-1] == ' ')) ci--;
                        command[ci] = 0;
                    }
                }
            }
            // Fallback: look for function=bash followed by any command-like text
            if (ci == 0) {
                char *fn = strstr(tc_body, "bash");
                if (fn) {
                    // Take everything after "bash" that looks like a command
                    fn += 4;
                    while (*fn && (*fn == '>' || *fn == '\n' || *fn == ' ' || *fn == '"')) fn++;
                    while (*fn && *fn != '<' && *fn != '"' && ci < 4095) {
                        command[ci++] = *fn++;
                    }
                    while (ci > 0 && (command[ci-1] == '\n' || command[ci-1] == ' ')) ci--;
                    command[ci] = 0;
                }
            }

            if (ci == 0) break;

            // Show the command and ask for confirmation
            printf("\033[33m$ %s\033[0m\n", command);
            printf("\033[2m[execute? y/n] \033[0m");
            fflush(stdout);
            int ch = getchar();
            int rest;while ((rest=getchar()) != '\n' && rest != EOF) {}
            if (ch != 'y' && ch != 'Y') {
                printf("\033[2m[skipped]\033[0m\n");
                free(response);
                response = NULL;
                break;
            }

            // Execute
            FILE *proc = popen(command, "r");
            char output[65536] = {0};
            int out_len = 0;
            if (proc) {
                while (out_len < 65535) {
                    int ch = fgetc(proc);
                    if (ch == EOF) break;
                    output[out_len++] = (char)ch;
                }
                output[out_len] = 0;
                pclose(proc);
            }

            // Print output
            if (out_len > 0) {
                printf("\033[2m%s\033[0m", output);
                if (output[out_len-1] != '\n') printf("\n");
            }

            // Send tool response back to model as a continuation
            // Format: <tool_response>\n{output}\n</tool_response>
            char *tool_msg = malloc(out_len + 256);
            snprintf(tool_msg, out_len + 256, "<tool_response>\n%s</tool_response>", output);

            // Tool output becomes a user turn, and is replayed at most once
            // after invalidation. Never re-execute a shell command on retry.
            NSMutableArray *tool_history = read_transcript(session_id);
            if (!tool_history) { free(tool_msg); free(response); response = NULL; break; }
            NSDictionary *tool_turn = @{@"role":@"user", @"content":@(tool_msg)};
            [tool_history addObject:tool_turn];
            free(response); response = NULL;
            // Persist before contacting the model: disconnect/replay must never
            // require running the already-approved command a second time.
            NSMutableDictionary *pendingRecord=[tool_turn mutableCopy];pendingRecord[@"anchor_count"]=@(tool_history.count-1);
            NSData *savedOutput=[NSJSONSerialization dataWithJSONObject:pendingRecord options:0 error:NULL];
            if(![savedOutput writeToFile:pending_path options:NSDataWritingAtomic error:NULL]) {
                fprintf(stderr,"[chat] Could not preserve tool output; stopping.\n");free(tool_msg);return 1;
            }
            response=perform_turn(port,tool_history,tool_turn,max_tokens,server_session_id,&server_session_live,show_thinking);
            if(response) {
                if(!session_commit_exchange(session_id,[tool_history subarrayWithRange:NSMakeRange(0,tool_history.count-1)],tool_turn,response)) {fprintf(stderr,"[chat] Tool transcript commit failed.\n");free(tool_msg);free(response);return 1;}
                [[NSFileManager defaultManager] removeItemAtPath:pending_path error:NULL];
            } else {
                // Preserve already executed output even if follow-up failed. No
                // automatic command execution/retry: save the exact replay input.
                fprintf(stderr,"[chat] Tool follow-up failed; retry requires the saved pending output.\n");

            }
            free(tool_msg);
        }

        free(response);
    }

    return 0;
}
