#include <stdio.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
static int opened, synced, closed, fail_open, fail_sync, fail_close;
static int fake_open(const char *path, int flags, ...) {(void)path;(void)flags;opened++;if(fail_open){errno=EACCES;return -1;}return 42;}
static int fake_fsync(int fd) {(void)fd;synced++;if(fail_sync){errno=EIO;return -1;}return 0;}
static int fake_close(int fd) {(void)fd;closed++;if(fail_close){errno=EBADF;return -1;}return 0;}
#define open fake_open
#define fsync fake_fsync
#define close fake_close
#include "warm_checkpoint_durability.h"
int main(void) {
 int failures=0,cases=0;
 for(int a=0;a<2;a++)for(int b=0;b<2;b++)for(int c=0;c<2;c++) {
  fail_open=a;fail_sync=b;fail_close=c;opened=synced=closed=0;errno=0;cases++;
  int result=warm_checkpoint_sync_directory("synthetic");
  if(result!=(!a&&!b&&!c)||opened!=1||synced!=(!a)||closed!=(!a)||(!result&&errno!=(a?EACCES:b?EIO:EBADF)))failures++;
 }
 printf("checkpoint directory durability cases=%d failures=%d\n",cases,failures);
 return failures?1:0;
}
