// Compile-time-only tool stub. No shell process can be launched by this binary.
#import <Foundation/Foundation.h>
#include <stdio.h>
static FILE *fixture_popen(const char *command,const char *mode) {
    (void)command;(void)mode;
    static char data[]="SYNTHETIC_TOOL_OUTPUT\n";
    fprintf(stderr,"TEST_TOOL_STUB_CALLED\n");
    return fmemopen(data,sizeof(data)-1,"r");
}
#define popen fixture_popen
#define pclose fclose
#define main chat_fixture_main
#include "../metal_infer/chat.m"
#undef main
int main(int argc,char **argv){return chat_fixture_main(argc,argv);}
