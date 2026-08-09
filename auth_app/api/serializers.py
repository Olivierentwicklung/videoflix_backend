from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.settings import api_settings as simplejwt_settings

User = get_user_model()


class PasswordResetRequestSerializer(serializers.Serializer):
    """Validate and normalize a password-reset email address."""

    email = serializers.EmailField(
        required=True,
        allow_blank=False,
        write_only=True,
    )

    def validate_email(self, value):
        """Apply the user model's standard email normalization."""
        return User.objects.normalize_email(value)  # type:ignore


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
