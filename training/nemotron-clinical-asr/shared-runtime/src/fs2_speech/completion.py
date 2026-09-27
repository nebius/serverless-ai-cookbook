"""Native CUDA completion fence, including calls which raise after submission."""


class NativeCompletionFence:
    def __init__(self):
        self.unsafe = False

    def require_safe(self):
        if self.unsafe:
            raise RuntimeError("native_buffers_quarantined")

    def call(self, function, synchronize, *args):
        self.require_safe()
        failed = False
        try:
            return function(*args)
        except Exception:
            failed = True
            # Native details are never returned to customers or diagnostics.
            raise RuntimeError("native_action_failed") from None
        finally:
            try:
                synchronize()
            except Exception:
                # Keep live handles/buffers referenced; no reset/reuse is safe
                # until process replacement. The scheduler also poisons itself.
                self.unsafe = True
                reason = "native_action_and_synchronization_failed" if failed else "native_synchronization_failed"
                raise RuntimeError(reason) from None
