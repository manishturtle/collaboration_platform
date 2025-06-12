# apps/chat/tests/test_api_channels.py

from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from ..models import ChatChannel, ChannelParticipant

User = get_user_model()


class ChannelAPITestCase(APITestCase):
    """
    Test cases for the Channel API endpoints.
    """
    
    def setUp(self):
        """
        Set up test data: users and client with authentication
        """
        # Create test users for a multi-tenant environment
        self.company_id = 1
        self.client_id = 1
        
        # Create users
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='user1@example.com',
            password='password123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='user2@example.com',
            password='password123'
        )
        self.user3 = User.objects.create_user(
            username='testuser3',
            email='user3@example.com',
            password='password123'
        )
        
        # Create an authenticated client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user1)
        
        # URL for channels list
        self.channels_url = reverse('channel-list')
        
    def test_list_channels_empty(self):
        """Test that a user with no channels gets an empty list"""
        response = self.client.get(self.channels_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
    
    def test_create_direct_channel(self):
        """Test creating a direct channel between two users"""
        data = {
            'participants': [self.user2.id],  # Only specify the other user
        }
        response = self.client.post(self.channels_url, data, format='json')
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['channel_type'], ChatChannel.ChannelType.DIRECT)
        self.assertIsNone(response.data['name'])  # Direct channels don't need names
        
        # Check database state
        channel_id = response.data['id']
        channel = ChatChannel.objects.get(id=channel_id)
        self.assertEqual(channel.channel_type, ChatChannel.ChannelType.DIRECT)
        
        # Verify participants - should be 2 (creator and the other user)
        participants = ChannelParticipant.objects.filter(channel=channel)
        self.assertEqual(participants.count(), 2)
        
        # Creator should be admin
        creator_participation = participants.get(user=self.user1)
        self.assertEqual(creator_participation.role, ChannelParticipant.Role.ADMIN)
        
        # Other user should be member
        other_participation = participants.get(user=self.user2)
        self.assertEqual(other_participation.role, ChannelParticipant.Role.MEMBER)
    
    def test_create_group_channel(self):
        """Test creating a group channel with multiple participants"""
        data = {
            'name': 'Test Group',
            'participants': [self.user2.id, self.user3.id],
        }
        response = self.client.post(self.channels_url, data, format='json')
        
        # Check response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['channel_type'], ChatChannel.ChannelType.GROUP)
        self.assertEqual(response.data['name'], 'Test Group')
        
        # Check database state
        channel_id = response.data['id']
        channel = ChatChannel.objects.get(id=channel_id)
        self.assertEqual(channel.channel_type, ChatChannel.ChannelType.GROUP)
        
        # Verify participants - should be 3 (creator and the two other users)
        participants = ChannelParticipant.objects.filter(channel=channel)
        self.assertEqual(participants.count(), 3)
        
        # Creator should be admin
        creator_participation = participants.get(user=self.user1)
        self.assertEqual(creator_participation.role, ChannelParticipant.Role.ADMIN)
    
    def test_retrieve_channel(self):
        """Test retrieving a specific channel"""
        # First create a channel
        data = {
            'name': 'Test Group Channel',
            'participants': [self.user2.id, self.user3.id],  # Multiple users makes it a group
        }
        create_response = self.client.post(self.channels_url, data, format='json')
        channel_id = create_response.data['id']
        
        # Now retrieve it
        detail_url = reverse('channel-detail', kwargs={'pk': channel_id})
        response = self.client.get(detail_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], channel_id)
        self.assertEqual(response.data['name'], 'Test Group Channel')
        
    def test_unauthorized_access(self):
        """Test that unauthenticated requests are rejected"""
        # Create an unauthenticated client
        unauthenticated_client = APIClient()
        
        # Try to access the channels list
        response = unauthenticated_client.get(self.channels_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    def test_channel_visibility_isolation(self):
        """Test that users can only see channels they are participants of"""
        # Create a channel with user2 (not including self.user1)
        other_client = APIClient()
        other_client.force_authenticate(user=self.user2)
        
        # User2 creates a channel with user3 (not including user1)
        data = {
            'name': 'Private Channel',
            'participants': [self.user3.id],
        }
        other_client.post(self.channels_url, data, format='json')
        
        # User1 should not see this channel
        response = self.client.get(self.channels_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)  # User1 has no channels
        
    def test_create_channel_validation(self):
        """Test validation errors when creating a channel"""
        # Try to create a channel without participants
        data = {
            'name': 'Invalid Channel',
            'participants': [],
        }
        response = self.client.post(self.channels_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
