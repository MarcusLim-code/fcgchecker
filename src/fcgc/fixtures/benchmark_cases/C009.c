#include <stdint.h>
typedef struct { uint32_t sample; uint32_t threshold; } State;
int hardware_init(State *state);
void enable_device_and_irq(State *state);
int start(State *state) {
    *state = (State){0};
    state->threshold = 7u;
    int rc = hardware_init(state);
    if (rc != 0) return rc;
    enable_device_and_irq(state);
    return 0;
}
