#include <stddef.h>
#include <stdint.h>
int lock_dma(void);
void unlock_dma(void);
int dma_submit(const void *data, size_t bytes);
int transfer(const void *data, size_t bytes) {
    if (((uintptr_t)data & 3u) != 0u || (bytes & 3u) != 0u) return -1;
    if (lock_dma() != 0) return -2;
    int rc = dma_submit(data, bytes);
    unlock_dma();
    return rc;
}
