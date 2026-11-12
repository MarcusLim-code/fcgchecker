#include <stddef.h>
int lock_dma(void);
void unlock_dma(void);
int dma_submit(const void *data, size_t bytes);
int transfer(const void *data, size_t bytes) {
    if (lock_dma() != 0) return -2;
    int rc = dma_submit(data, bytes);
    if (rc != 0) return rc;
    unlock_dma();
    return 0;
}
