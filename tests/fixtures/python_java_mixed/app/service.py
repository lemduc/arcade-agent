"""Python service that must not be linked to the Java entities."""

import com.auth.service


class PaymentHandler(Base):  # noqa: F821 — unresolvable on purpose (fixture)
    """Extends a Base that does not exist in Python land."""

    def login(self):
        return com.auth.service
