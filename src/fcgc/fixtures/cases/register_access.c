#include <stdint.h>

void register_access(uint32_t value) {
    volatile uint32_t *register_ptr = (volatile uint32_t *)0x40001000u;
    *register_ptr = value;
}
