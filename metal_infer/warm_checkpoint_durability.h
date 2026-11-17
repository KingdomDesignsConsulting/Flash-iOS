#ifndef FLASH_WARM_CHECKPOINT_DURABILITY_H
#define FLASH_WARM_CHECKPOINT_DURABILITY_H
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
/* Called after file fsync + rename. Failure means visible, NOT confirmed durable;
 * it cannot restore an overwritten target. Caller must not prune older states. */
static inline int warm_checkpoint_sync_directory(const char *directory) {
    int fd = open(directory, O_RDONLY);
    if (fd < 0) return 0;
    int ok = fsync(fd) == 0;
    int saved = errno;
    if (close(fd) != 0) { if (ok) saved = errno; ok = 0; }
    if (!ok) errno = saved;
    return ok;
}
#endif
