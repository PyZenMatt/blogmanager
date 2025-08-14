import pytest
from django.db import IntegrityError, OperationalError, DataError
from rest_framework import status
from rest_framework.test import APIRequestFactory
from blog_manager.exceptions import custom_exception_handler

def test_custom_exception_handler_db_errors():
    """Test that DB errors are mapped to 400 responses"""
    factory = APIRequestFactory()
    request = factory.get('/')
    context = {'request': request, 'view': 'test_view'}
    
    # Test OperationalError (charset issues)
    exc = OperationalError("Incorrect string value")
    response = custom_exception_handler(exc, context)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Input non valido" in str(response.data["detail"])
    
    # Test IntegrityError
    exc = IntegrityError("Duplicate key")
    response = custom_exception_handler(exc, context)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    # Test DataError
    exc = DataError("Data too long")
    response = custom_exception_handler(exc, context)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_custom_exception_handler_other_errors():
    """Test that non-DB errors are handled by default handler"""
    from rest_framework.views import exception_handler
    
    factory = APIRequestFactory()
    request = factory.get('/')
    context = {'request': request, 'view': 'test_view'}
    
    # Test ValueError (should use default handler)
    exc = ValueError("Some error")
    response = custom_exception_handler(exc, context)
    expected_response = exception_handler(exc, context)
    
    # Both should be None (not handled by either)
    assert response == expected_response