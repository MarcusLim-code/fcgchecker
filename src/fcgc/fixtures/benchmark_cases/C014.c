#include <stddef.h>
#include <stdint.h>
int sum_bytes(const uint8_t *buffer, size_t length) {
    if (length == 0u) return 0;
    int sum = 0;
    for (size_t i = 0; i < length; ++i) sum += buffer[i];
    return sum;
}
