from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class BookmarkFolder(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(default='', blank=True)

    def __str__(self):
        return self.name


class BookmarkFolderUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(BookmarkFolder, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class BookmarkFolderGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(BookmarkFolder, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicBookmarkFolder(models.Model):

    bookmarkfolder = models.OneToOneField(BookmarkFolder, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.bookmarkfolder, 'public' if self.public else 'private')


@receiver(post_save, sender=BookmarkFolder, weak=False, dispatch_uid="create_bookmarkfolder_public_object")
def create_bookmarkfolder_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public bookmarkfolder object.
    """
    if created:
        PublicBookmarkFolder.objects.create(bookmarkfolder=instance)


class Bookmark(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(default='', blank=True)
    url = models.URLField(max_length=2000)
    created = models.DateTimeField(auto_now=True)
    bookmarkfolder = models.ForeignKey(BookmarkFolder, on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class BookmarkUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(Bookmark, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class BookmarkGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(Bookmark, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicBookmark(models.Model):

    bookmark = models.OneToOneField(Bookmark, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.bookmark, 'public' if self.public else 'private')


@receiver(post_save, sender=Bookmark, weak=False, dispatch_uid="create_bookmark_public_object")
def create_bookmark_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public bookmark object.
    """
    if created:
        PublicBookmark.objects.create(bookmark=instance)
