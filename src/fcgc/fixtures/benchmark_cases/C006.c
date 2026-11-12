#include <stddef.h>
#include <stdint.h>
size_t external_read_count(void);
void copy_samples(uint8_t *dst, const uint8_t *src, size_t capacity) {
    size_t count = external_read_count();
    for (size_t i = 0; i <= count; ++i) dst[i] = src[i];
    (void)capacity;
}
