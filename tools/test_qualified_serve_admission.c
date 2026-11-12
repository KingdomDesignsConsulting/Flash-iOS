/* Model-free admission regression: clang/cc -std=c11 -Wall -Wextra -Werror -I metal_infer tools/test_qualified_serve_admission.c -o /tmp/flash-admission-test && /tmp/flash-admission-test */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "flash_serve_admission.h"
int main(void) {
    assert(flash_serve_policy_mode(NULL) == 0);
    assert(flash_serve_policy_mode("") == -1);
    assert(flash_serve_policy_mode("1") == 1);
    assert(flash_serve_policy_mode("0") == -1);
    assert(flash_serve_policy_mode("true") == -1);
    assert(flash_serve_policy_mode(" ") == -1);
    assert(flash_serve_policy_mode(" 1") == -1);
    assert(flash_serve_context_admitted(0, 32768, 0, 65536, 32768));
    assert(flash_serve_context_admitted(32767, 0, 1, 65536, 32768));
    assert(!flash_serve_context_admitted(32768, 1, 1, 65536, 32768));
    assert(!flash_serve_context_admitted(32768, 0, 1, 65536, 32768));
    assert(!flash_serve_context_admitted(32767, 0, 2, 65536, 32768));
    assert(!flash_serve_context_admitted(-1, 1, 1, 65536, 32768));
    assert(!flash_serve_context_admitted(0, -1, 1, 65536, 32768));
    assert(!flash_serve_context_admitted(INT32_MAX, INT32_MAX, INT32_MAX, 65536, 32768));
    assert(!flash_serve_context_admitted(8192, 1, 0, 65536, 8192));
    assert(flash_serve_context_admitted(8192, 0, 0, 65536, 8192));
    assert(flash_serve_host_reserve_admitted(FLASH_SERVE_MIN_HOST_AVAILABLE_BYTES));
    assert(!flash_serve_host_reserve_admitted(FLASH_SERVE_MIN_HOST_AVAILABLE_BYTES - 1));
    puts("qualified serve admission: 19 model-free cases PASS");
    return 0;
}
