#include <stddef.h>
#include <stdint.h>
size_t external_read_count(void);
void copy_samples(uint8_t *dst, const uint8_t *src, size_t capacity) {
    if (dst == NULL || src == NULL) return;
    size_t count = external_read_count();
    if (count > capacity) count = capacity;
    for (size_t i = 0; i < count; ++i) dst[i] = src[i];
}
