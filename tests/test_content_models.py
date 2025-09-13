# tests/test_content_models.py
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError

from content.models import MediaCategory, MediaAsset
from common.enums import AssetType
from tests.factories import UserFactory


@pytest.mark.django_db
class TestContentModels:

    def test_media_category_creation_and_str(self):
        """Test MediaCategory model creation and string representation"""
        category = MediaCategory.objects.create(name="Product Images")
        
        assert str(category) == "Product Images"
        assert category.name == "Product Images"
        
        # Test BaseModel inheritance
        assert hasattr(category, 'created_at')
        assert hasattr(category, 'updated_at')
        assert hasattr(category, 'uuid')

    def test_media_asset_creation_with_file(self):
        """Test MediaAsset creation with file upload"""
        user = UserFactory()
        category = MediaCategory.objects.create(name="Photos")
        
        # Create a simple test file
        test_file = SimpleUploadedFile(
            "test_image.jpg",
            b"fake image content",
            content_type="image/jpeg"
        )
        
        asset = MediaAsset.objects.create(
            title="Test Image",
            description="A test image for testing",
            caption="Test caption",
            alt_text="Alternative text for accessibility",
            asset_type=AssetType.PHOTO,
            file=test_file,
            size="1.2 MB",
            dimensions="1920x1080",
            category=category,
            uploaded_by=user
        )
        
        assert str(asset) == "Test Image"
        assert asset.title == "Test Image"
        assert asset.description == "A test image for testing"
        assert asset.caption == "Test caption"
        assert asset.alt_text == "Alternative text for accessibility"
        assert asset.asset_type == AssetType.PHOTO
        assert "test_image" in asset.file.name
        assert asset.file.name.endswith(".jpg")
        assert asset.size == "1.2 MB"
        assert asset.dimensions == "1920x1080"
        assert asset.category == category
        assert asset.uploaded_by == user
        assert asset.external_url is None

    def test_media_asset_with_external_url(self):
        """Test MediaAsset with external URL instead of file"""
        user = UserFactory()
        
        asset = MediaAsset.objects.create(
            title="External Video",
            asset_type=AssetType.VIDEO,
            external_url="https://youtube.com/watch?v=example",
            uploaded_by=user
        )
        
        assert asset.title == "External Video"
        assert asset.asset_type == AssetType.VIDEO
        assert asset.external_url == "https://youtube.com/watch?v=example"
        assert not asset.file  # Should be empty/None

    def test_media_asset_different_types(self):
        """Test MediaAsset with different asset types"""
        user = UserFactory()
        
        # Photo
        photo = MediaAsset.objects.create(
            title="Photo Asset",
            asset_type=AssetType.PHOTO,
            uploaded_by=user
        )
        assert photo.asset_type == AssetType.PHOTO
        
        # Video  
        video = MediaAsset.objects.create(
            title="Video Asset",
            asset_type=AssetType.VIDEO,
            uploaded_by=user
        )
        assert video.asset_type == AssetType.VIDEO
        
        # Document
        document = MediaAsset.objects.create(
            title="Document Asset",
            asset_type=AssetType.DOCUMENT,
            uploaded_by=user
        )
        assert document.asset_type == AssetType.DOCUMENT

    def test_media_asset_without_category(self):
        """Test MediaAsset can be created without category"""
        user = UserFactory()
        
        asset = MediaAsset.objects.create(
            title="Uncategorized Asset",
            uploaded_by=user
        )
        
        assert asset.category is None
        assert asset.title == "Uncategorized Asset"

    def test_media_asset_without_user(self):
        """Test MediaAsset can be created without uploaded_by user"""
        asset = MediaAsset.objects.create(
            title="System Asset"
        )
        
        assert asset.uploaded_by is None
        assert asset.title == "System Asset"

    def test_media_asset_default_asset_type(self):
        """Test MediaAsset has default asset type of PHOTO"""
        asset = MediaAsset.objects.create(
            title="Default Type Asset"
        )
        
        assert asset.asset_type == AssetType.PHOTO

    def test_media_asset_blank_fields(self):
        """Test MediaAsset handles blank optional fields"""
        asset = MediaAsset.objects.create(
            title="Minimal Asset"
        )
        
        assert asset.description == ""
        assert asset.caption == ""
        assert asset.alt_text == ""
        assert asset.size == ""
        assert asset.dimensions == ""
        assert asset.external_url is None

    def test_media_category_relationship_with_assets(self):
        """Test MediaCategory relationship with MediaAssets"""
        category = MediaCategory.objects.create(name="Marketing Materials")
        user = UserFactory()
        
        asset1 = MediaAsset.objects.create(
            title="Banner 1",
            category=category,
            uploaded_by=user
        )
        
        asset2 = MediaAsset.objects.create(
            title="Banner 2", 
            category=category,
            uploaded_by=user
        )
        
        # Test reverse relationship
        assets = category.media_assets.all()
        assert asset1 in assets
        assert asset2 in assets
        assert assets.count() == 2

    def test_media_category_set_null_on_delete(self):
        """Test MediaAsset category is set to null when category is deleted"""
        category = MediaCategory.objects.create(name="Temp Category")
        user = UserFactory()
        
        asset = MediaAsset.objects.create(
            title="Test Asset",
            category=category,
            uploaded_by=user
        )
        
        # Delete category
        category.delete()
        asset.refresh_from_db()
        
        # Asset should still exist but category should be null
        assert asset.category is None
        assert asset.title == "Test Asset"

    def test_user_set_null_on_delete(self):
        """Test MediaAsset uploaded_by is set to null when user is deleted"""
        user = UserFactory()
        
        asset = MediaAsset.objects.create(
            title="User Asset",
            uploaded_by=user
        )
        
        # Delete user
        user.delete()
        asset.refresh_from_db()
        
        # Asset should still exist but uploaded_by should be null
        assert asset.uploaded_by is None
        assert asset.title == "User Asset"

    def test_media_asset_with_all_fields(self):
        """Test MediaAsset creation with all fields populated"""
        user = UserFactory()
        category = MediaCategory.objects.create(name="Complete Category")
        
        test_file = SimpleUploadedFile(
            "complete_test.pdf",
            b"fake pdf content",
            content_type="application/pdf"
        )
        
        asset = MediaAsset.objects.create(
            title="Complete Asset",
            description="Complete description with all fields",
            caption="Complete caption",
            alt_text="Complete alt text",
            asset_type=AssetType.DOCUMENT,
            file=test_file,
            external_url="https://backup.example.com/file.pdf",
            size="2.5 MB",
            dimensions="A4",
            category=category,
            uploaded_by=user
        )
        
        # Verify all fields are set correctly
        assert asset.title == "Complete Asset"
        assert asset.description == "Complete description with all fields"
        assert asset.caption == "Complete caption"
        assert asset.alt_text == "Complete alt text"
        assert asset.asset_type == AssetType.DOCUMENT
        assert "complete_test" in asset.file.name
        assert asset.file.name.endswith(".pdf")
        assert asset.external_url == "https://backup.example.com/file.pdf"
        assert asset.size == "2.5 MB"
        assert asset.dimensions == "A4"
        assert asset.category == category
        assert asset.uploaded_by == user

    def test_base_model_inheritance(self):
        """Test both models inherit BaseModel functionality"""
        category = MediaCategory.objects.create(name="Inheritance Test")
        asset = MediaAsset.objects.create(title="Inheritance Test Asset")
        
        for obj in [category, asset]:
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
