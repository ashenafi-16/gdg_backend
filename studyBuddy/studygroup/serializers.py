from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Subject, StudyGroup, GroupMembership,
    Session, GroupChat, ChatAttachment
)
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from drf_spectacular.utils import extend_schema_serializer, extend_schema_field
from typing import Dict, Any, List

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'avatar']
        extra_kwargs = {
            'password': {'write_only': True}
        }


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        data = super().validate(attrs)
        data.update({
            'user': UserSerializer(self.user).data
        })
        return data


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'description', 'icon', 'color']


class GroupMembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = GroupMembership
        fields = ['id', 'user', 'role', 'joined_at', 'is_active']


@extend_schema_serializer(component_name="DashboardStudyGroup")
class StudyGroupSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    creator = UserSerializer(read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    last_activity = serializers.DateTimeField(read_only=True)
    is_member = serializers.SerializerMethodField()
    membership = serializers.SerializerMethodField()
    
    class Meta:
        model = StudyGroup
        fields = [
            'id', 'name', 'description', 'subject', 'creator',
            'avatar', 'privacy', 'created_at', 'updated_at',
            'member_count', 'last_activity', 'is_member', 'membership'
        ]
    
    def get_is_member(self, obj: StudyGroup) -> bool:
        request = self.context.get('request')
        return request and request.user.is_authenticated and obj.members.filter(id=request.user.id).exists()
    
    def get_membership(self, obj: StudyGroup) -> Dict[str, Any]:
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            membership = obj.memberships.filter(user=request.user).first()
            return GroupMembershipSerializer(membership).data if membership else None
        return None


class StudyGroupCreateSerializer(serializers.ModelSerializer):
    subject_id = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(),
        source='subject',
        write_only=True
    )
    
    class Meta:
        model = StudyGroup
        fields = ['name', 'description', 'subject_id', 'privacy']
    
    def create(self, validated_data: Dict[str, Any]) -> StudyGroup:
        validated_data['creator'] = self.context['request'].user
        return super().create(validated_data)


class SessionSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=StudyGroup.objects.all())
    created_by = UserSerializer(read_only=True)
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = Session
        fields = [
            'id', 'group', 'title', 'description', 'start_time', 'end_time',
            'location', 'created_by', 'status', 'max_attendees', 'is_virtual',
            'meeting_link', 'created_at', 'duration'
        ]
    
    def get_duration(self, obj: Session) -> str:
        return obj.duration


class ChatAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatAttachment
        fields = ['id', 'file', 'file_url', 'file_size', 'file_type', 'uploaded_at']
        read_only_fields = ['file_type', 'uploaded_at']

    @extend_schema_field(serializers.CharField())
    def get_file_url(self, obj: ChatAttachment) -> str:
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    @extend_schema_field(serializers.IntegerField())
    def get_file_size(self, obj: ChatAttachment) -> int:
        return obj.file.size if obj.file else 0


class GroupChatSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    group = serializers.PrimaryKeyRelatedField(queryset=StudyGroup.objects.all())
    attachments = ChatAttachmentSerializer(many=True, read_only=True)
    parent = serializers.PrimaryKeyRelatedField(queryset=GroupChat.objects.all(), required=False, allow_null=True)
    
    class Meta:
        model = GroupChat
        fields = [
            'id', 'group', 'user', 'message', 'created_at', 
            'updated_at', 'attachments', 'parent'
        ]
        read_only_fields = ['user', 'created_at', 'updated_at']
    
    def create(self, validated_data: Dict[str, Any]) -> GroupChat:
        attachments_data = self.context.get('request').FILES
        chat = GroupChat.objects.create(
            user=self.context['request'].user,
            **validated_data
        )
        
        for attachment in attachments_data.getlist('attachments'):
            ChatAttachment.objects.create(
                chat=chat,
                file=attachment
            )
        
        return chat