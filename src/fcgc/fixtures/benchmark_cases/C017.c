#include <stddef.h>
int flash_write(const void *buffer, size_t count);
int commit_flash(void);
#define STORE(bytes, count) flash_write((bytes), (count))
int persist(const void *data, size_t length) {
    int written = STORE(data, length);
    if (written < 0 || (size_t)written != length) return -1;
    return commit_flash();
}
