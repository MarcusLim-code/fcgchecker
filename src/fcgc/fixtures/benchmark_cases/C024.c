#include <stdint.h>
uint32_t rotate_mask(uint32_t value, unsigned count) {
    unsigned shift = count & 31u;
    if (shift == 0u) return value;
    return (value << shift) | (value >> (32u - shift));
}
