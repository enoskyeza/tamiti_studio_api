# tests/test_chatrooms_extended_models.py
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from chatrooms.models import (
    MessageFileUpload, DirectMessageFile, DirectThreadReadState,
    ChannelMessage, DirectMessage, DirectThread
)
from tests.factories import (
    UserFactory, ChannelFactory, ChannelMessageFactory,
    DirectThreadFactory, DirectMessageFactory
)


@pytest.mark.django_db
class TestChatroomsExtendedModels:

    def test_message_file_upload_creation_and_str(self):
        """Test MessageFileUpload model creation and string representation"""
        message = ChannelMessageFactory()
        
        # Create a test file
        test_file = SimpleUploadedFile(
            "test_document.pdf",
            b"fake pdf content",
            content_type="application/pdf"
        )
        
        upload = MessageFileUpload.objects.create(
            message=message,
            file=test_file
        )
        
        assert str(upload) == f"Attachment for message {message.id}"
        assert upload.message == message
        assert "test_document" in upload.file.name
        assert upload.file.name.endswith(".pdf")
        assert upload.uploaded_at is not None
        
        # Test BaseModel inheritance
        assert hasattr(upload, 'created_at')
        assert hasattr(upload, 'updated_at')
        assert hasattr(upload, 'uuid')

    def test_message_file_upload_cascade_on_message_delete(self):
        """Test MessageFileUpload is deleted when message is deleted"""
        message = ChannelMessageFactory()
        
        test_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake image content",
            content_type="image/jpeg"
        )
        
        upload = MessageFileUpload.objects.create(
            message=message,
            file=test_file
        )
        upload_id = upload.id
        
        # Delete message should cascade delete upload
        message.delete()
        assert not MessageFileUpload.objects.filter(id=upload_id).exists()

    def test_message_file_upload_relationship(self):
        """Test MessageFileUpload relationship with ChannelMessage"""
        message = ChannelMessageFactory()
        
        # Create multiple attachments
        file1 = SimpleUploadedFile("doc1.txt", b"content1", content_type="text/plain")
        file2 = SimpleUploadedFile("doc2.txt", b"content2", content_type="text/plain")
        
        upload1 = MessageFileUpload.objects.create(message=message, file=file1)
        upload2 = MessageFileUpload.objects.create(message=message, file=file2)
        
        # Test reverse relationship
        attachments = message.attachments.all()
        assert upload1 in attachments
        assert upload2 in attachments
        assert attachments.count() == 2

    def test_direct_message_file_creation_and_str(self):
        """Test DirectMessageFile model creation and string representation"""
        dm = DirectMessageFactory()
        
        test_file = SimpleUploadedFile(
            "private_doc.docx",
            b"private document content",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        dm_file = DirectMessageFile.objects.create(
            message=dm,
            file=test_file
        )
        
        assert str(dm_file) == f"Direct attachment for message {dm.id}"
        assert dm_file.message == dm
        assert "private_doc" in dm_file.file.name
        assert dm_file.file.name.endswith(".docx")
        assert dm_file.uploaded_at is not None

    def test_direct_message_file_cascade_on_message_delete(self):
        """Test DirectMessageFile is deleted when DirectMessage is deleted"""
        dm = DirectMessageFactory()
        
        test_file = SimpleUploadedFile(
            "test_attachment.zip",
            b"fake zip content",
            content_type="application/zip"
        )
        
        dm_file = DirectMessageFile.objects.create(
            message=dm,
            file=test_file
        )
        dm_file_id = dm_file.id
        
        # Delete direct message should cascade delete file
        dm.delete()
        assert not DirectMessageFile.objects.filter(id=dm_file_id).exists()

    def test_direct_message_file_relationship(self):
        """Test DirectMessageFile relationship with DirectMessage"""
        dm = DirectMessageFactory()
        
        # Create multiple attachments
        file1 = SimpleUploadedFile("attachment1.pdf", b"pdf1", content_type="application/pdf")
        file2 = SimpleUploadedFile("attachment2.pdf", b"pdf2", content_type="application/pdf")
        
        dm_file1 = DirectMessageFile.objects.create(message=dm, file=file1)
        dm_file2 = DirectMessageFile.objects.create(message=dm, file=file2)
        
        # Test reverse relationship
        attachments = dm.attachments.all()
        assert dm_file1 in attachments
        assert dm_file2 in attachments
        assert attachments.count() == 2

    def test_direct_thread_read_state_creation_and_str(self):
        """Test DirectThreadReadState model creation and string representation"""
        thread = DirectThreadFactory()
        user = UserFactory()
        last_read = timezone.now()
        
        read_state = DirectThreadReadState.objects.create(
            thread=thread,
            user=user,
            last_read_at=last_read
        )
        
        expected_str = f"ReadState(thread={thread.id}, user={user.id}, last_read_at={last_read})"
        assert str(read_state) == expected_str
        assert read_state.thread == thread
        assert read_state.user == user
        assert read_state.last_read_at == last_read

    def test_direct_thread_read_state_without_last_read(self):
        """Test DirectThreadReadState can be created without last_read_at"""
        thread = DirectThreadFactory()
        user = UserFactory()
        
        read_state = DirectThreadReadState.objects.create(
            thread=thread,
            user=user
        )
        
        assert read_state.last_read_at is None
        expected_str = f"ReadState(thread={thread.id}, user={user.id}, last_read_at=None)"
        assert str(read_state) == expected_str

    def test_direct_thread_read_state_unique_constraint(self):
        """Test DirectThreadReadState unique constraint per thread and user"""
        thread = DirectThreadFactory()
        user = UserFactory()
        
        read_state1 = DirectThreadReadState.objects.create(
            thread=thread,
            user=user,
            last_read_at=timezone.now()
        )
        
        # Creating another read state for same thread and user should fail
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            DirectThreadReadState.objects.create(
                thread=thread,
                user=user,
                last_read_at=timezone.now()
            )

    def test_direct_thread_read_state_cascade_on_thread_delete(self):
        """Test DirectThreadReadState is deleted when thread is deleted"""
        thread = DirectThreadFactory()
        user = UserFactory()
        
        read_state = DirectThreadReadState.objects.create(
            thread=thread,
            user=user
        )
        read_state_id = read_state.id
        
        # Delete thread should cascade delete read state
        thread.delete()
        assert not DirectThreadReadState.objects.filter(id=read_state_id).exists()

    def test_direct_thread_read_state_cascade_on_user_delete(self):
        """Test DirectThreadReadState is deleted when user is deleted"""
        thread = DirectThreadFactory()
        user = UserFactory()
        
        read_state = DirectThreadReadState.objects.create(
            thread=thread,
            user=user
        )
        read_state_id = read_state.id
        
        # Delete user should cascade delete read state
        user.delete()
        assert not DirectThreadReadState.objects.filter(id=read_state_id).exists()

    def test_direct_thread_read_state_relationships(self):
        """Test DirectThreadReadState relationships"""
        thread = DirectThreadFactory()
        user1 = UserFactory()
        user2 = UserFactory()
        
        # Create read states for both users in the thread
        read_state1 = DirectThreadReadState.objects.create(
            thread=thread,
            user=user1,
            last_read_at=timezone.now()
        )
        
        read_state2 = DirectThreadReadState.objects.create(
            thread=thread,
            user=user2
        )
        
        # Test reverse relationships
        thread_read_states = thread.read_states.all()
        assert read_state1 in thread_read_states
        assert read_state2 in thread_read_states
        assert thread_read_states.count() == 2
        
        user1_read_states = user1.direct_thread_read_states.all()
        assert read_state1 in user1_read_states
        assert read_state2 not in user1_read_states
        assert user1_read_states.count() == 1

    def test_multiple_file_uploads_per_message(self):
        """Test multiple file uploads per message"""
        message = ChannelMessageFactory()
        
        # Create multiple files
        files = []
        uploads = []
        for i in range(3):
            file = SimpleUploadedFile(
                f"file_{i}.txt",
                f"content {i}".encode(),
                content_type="text/plain"
            )
            files.append(file)
            
            upload = MessageFileUpload.objects.create(
                message=message,
                file=file
            )
            uploads.append(upload)
        
        # Verify all uploads are associated with the message
        message_attachments = message.attachments.all()
        assert message_attachments.count() == 3
        
        for upload in uploads:
            assert upload in message_attachments

    def test_file_upload_auto_timestamp(self):
        """Test file upload timestamps are automatically set"""
        message = ChannelMessageFactory()
        
        test_file = SimpleUploadedFile(
            "timestamp_test.txt",
            b"test content",
            content_type="text/plain"
        )
        
        before_upload = timezone.now()
        upload = MessageFileUpload.objects.create(
            message=message,
            file=test_file
        )
        after_upload = timezone.now()
        
        # uploaded_at should be between before and after
        assert before_upload <= upload.uploaded_at <= after_upload

    def test_direct_message_file_auto_timestamp(self):
        """Test DirectMessageFile timestamps are automatically set"""
        dm = DirectMessageFactory()
        
        test_file = SimpleUploadedFile(
            "dm_timestamp_test.txt",
            b"dm test content",
            content_type="text/plain"
        )
        
        before_upload = timezone.now()
        dm_file = DirectMessageFile.objects.create(
            message=dm,
            file=test_file
        )
        after_upload = timezone.now()
        
        # uploaded_at should be between before and after
        assert before_upload <= dm_file.uploaded_at <= after_upload

    def test_base_model_inheritance(self):
        """Test all models inherit BaseModel functionality"""
        message = ChannelMessageFactory()
        dm = DirectMessageFactory()
        thread = DirectThreadFactory()
        user = UserFactory()
        
        test_file1 = SimpleUploadedFile("test1.txt", b"content1", content_type="text/plain")
        test_file2 = SimpleUploadedFile("test2.txt", b"content2", content_type="text/plain")
        
        upload = MessageFileUpload.objects.create(message=message, file=test_file1)
        dm_file = DirectMessageFile.objects.create(message=dm, file=test_file2)
        read_state = DirectThreadReadState.objects.create(thread=thread, user=user)
        
        for obj in [upload, dm_file, read_state]:
            # Check BaseModel fields
            assert hasattr(obj, 'created_at')
            assert hasattr(obj, 'updated_at')
            assert hasattr(obj, 'deleted_at')
            assert hasattr(obj, 'is_deleted')
            assert hasattr(obj, 'uuid')
            
            # Check soft delete method
            assert hasattr(obj, 'soft_delete')
            
            # Test soft delete functionality
            obj.soft_delete()
            assert obj.is_deleted is True
            assert obj.deleted_at is not None
