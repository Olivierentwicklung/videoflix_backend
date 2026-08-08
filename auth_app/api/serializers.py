from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    """Validate registration data and create an inactive user account."""

    confirmed_password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    class Meta:
        """Configure the user model fields exposed during registration."""

        model = User
        fields = ('email', 'password', 'confirmed_password')
        extra_kwargs = {
            'email': {
                'required': True,
                'allow_blank': False,
            },
            'password': {
                'required': True,
                'allow_blank': False,
                'write_only': True,
                'trim_whitespace': False,
            },
        }

    def validate_email(self, value):
        """Normalize the email and reject case-insensitive duplicates."""
        normalized_email = User.objects.normalize_email(value)  # type:ignore

        if User.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError(
                'A user with this email address already exists.'
            )

        return normalized_email

    def validate(self, attrs):
        """Ensure that the password and confirmation match."""
        if attrs['password'] != attrs['confirmed_password']:
            raise serializers.ValidationError(
                {'confirmed_password': 'Passwords do not match.'}
            )
        return attrs

    def create(self, validated_data):
        """Create an inactive user with a securely hashed password."""
        validated_data.pop('confirmed_password')
        email = validated_data['email']

        user_fields = {
            'username': email,
            'email': email,
            'password': validated_data['password'],
            'is_active': False,
        }

        return User.objects.create_user(**user_fields)  # type:ignore
