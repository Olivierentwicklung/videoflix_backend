from django.contrib.auth.tokens import PasswordResetTokenGenerator


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    """Generate activation tokens invalidated by account activation."""

    def _make_hash_value(self, user, timestamp):
        """Include activation state so a token can only be used once."""
        return f'{super()._make_hash_value(user, timestamp)}{user.is_active}'


account_activation_token = AccountActivationTokenGenerator()
