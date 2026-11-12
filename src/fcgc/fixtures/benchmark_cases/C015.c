#include <stddef.h>
void emit(char *destination, size_t capacity, const char *source, size_t length) {
    if (destination == 0 || source == 0 || capacity == 0u) return;
    size_t n = length < capacity ? length : capacity - 1u;
    for (size_t i = 0; i < n; ++i) destination[i] = source[i];
    destination[n] = 0;
}
