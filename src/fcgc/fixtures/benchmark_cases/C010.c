#include <stdint.h>
typedef struct { uint32_t sample; uint32_t threshold; } State;
int hardware_init(State *state);
void enable_device_and_irq(State *state);
int start(State *state) {
    enable_device_and_irq(state);
    int rc = hardware_init(state);
    if (rc != 0) return (int)state->sample;
    state->threshold = 7u;
    return 0;
}
