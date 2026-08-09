from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings as simplejwt_settings

User = get_user_model()


class PasswordResetRequestSerializer(  # pylint: disable=abstract-method
    serializers.Serializer
):
    """Validate and normalize a password-reset email address."""

    email = serializers.EmailField(
        required=True,
        allow_blank=False,
        write_only=True,
    )

    def validate_email(self, value):
        """Apply the user model's standard email normalization."""
        return User.objects.normalize_email(value)  # type:ignore


class PasswordConfirmSerializer(  # pylint: disable=abstract-method
    serializers.Serializer
):
    """Validate and apply a new password for a password-reset user."""

    new_password = serializers.CharField(
        required=True,
        allow_blank=False,
        write_only=True,
        trim_whitespace=False,
        style={'input_type': 'password'},
    )
    confirm_password = serializers.CharField(
        required=True,
        allow_blank=False,
        write_only=True,
        trim_whitespace=False,
        style={'input_type': 'password'},
    )

    def validate(self, attrs):
        """Require matching fields and enforce Django's password policy."""
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'Passwords do not match.'}
            )

        user = self.context['user']
        try:
            validate_password(attrs['new_password'], user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                {'new_password': error.messages}
            ) from error

        return attrs

    def save(self, **kwargs):
        """Hash and persist the validated password for the target user."""
        del kwargs
        user = self.context['user']
        user.set_password(self.validated_data['new_password'])  # type:ignore
        user.save(update_fields=['password'])
        return user


class LoginSerializer(TokenObtainPairSerializer):  # pylint: disable=abstract-method
    """Authenticate an active user by email and issue a JWT pair."""

    username_field = 'email'
    default_error_messages = {
        'no_active_account': 'Invalid email or password.',
    }

    def __init__(self, *args, **kwargs):
        """Expose the endpoint's email and password request fields."""
        super().__init__(*args, **kwargs)
        self.user = None
        self.fields['email'] = serializers.EmailField(write_only=True)
        self.fields['password'] = serializers.CharField(
            write_only=True,
            trim_whitespace=False,
            style={'input_type': 'password'},
        )

    def validate(self, attrs):
        """Authenticate case-insensitively without revealing account state."""
        normalized_email = User.objects.normalize_email(attrs['email'])  # type:ignore
        candidate = (
            User.objects.filter(email__iexact=normalized_email)  # type:ignore
            .only('username')
            .order_by('pk')
            .first()
        )
        username = candidate.get_username() if candidate else normalized_email
        user = authenticate(
            request=self.context.get('request'),
            username=username,
            password=attrs['password'],
        )

        if not simplejwt_settings.USER_AUTHENTICATION_RULE(user):  # type:ignore
            raise AuthenticationFailed(
                self.error_messages['no_active_account'],
                code='no_active_account',
            )

        self.user = user
        refresh = self.get_token(user)  # type:ignore

        return {
            'access': str(refresh.access_token),  # type:ignore
            'refresh': str(refresh),
            'detail': 'Login successful',
            'user': {
                'id': user.pk,  # type:ignore
                'username': user.get_username(),  # type:ignore
            },
        }


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
