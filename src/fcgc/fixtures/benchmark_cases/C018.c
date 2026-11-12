#include <stddef.h>
int flash_write(const void *buffer, size_t count);
int commit_flash(void);
#define STORE(bytes, count) flash_write((bytes), (count))
int persist(const void *data, size_t length) {
    STORE(data, length);
    return commit_flash();
}
