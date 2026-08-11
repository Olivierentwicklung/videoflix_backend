"""Django admin configuration for the video catalogue."""

from django.contrib import admin
from django import forms

from video_app.models import Category, Video


class VideoAdminForm(forms.ModelForm):
    """Require an original upload when an administrator creates a video."""

    class Meta:
        """Bind the form to all administrator-editable video fields."""

        model = Video
        fields = '__all__'

    def clean_original(self):
        """Reject new catalogue entries without a source video."""
        original = self.cleaned_data.get('original')
        if self.instance.pk is None and not original:
            raise forms.ValidationError('An original video is required.')
        return original


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Configure category management in the Django admin."""

    list_display = ('id', 'name')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    """Configure efficient video management in the Django admin."""

    form = VideoAdminForm
    list_display = ('id', 'title', 'category', 'processing_status', 'created_at')
    list_filter = ('category', 'processing_status', 'created_at')
    search_fields = ('title', 'description')
    ordering = ('-created_at',)
    list_select_related = ('category',)
    readonly_fields = (
        'storage_id',
        'thumbnail',
        'processing_status',
        'processing_error',
    )
