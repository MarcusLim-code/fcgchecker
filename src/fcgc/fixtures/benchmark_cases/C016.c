#include <stddef.h>
void emit(char *destination, size_t capacity, const char *source, size_t length) {
    size_t n = length < capacity ? length : capacity;
    for (size_t i = 0; i < n; ++i) destination[i] = source[i];
    destination[n] = 0;
}
