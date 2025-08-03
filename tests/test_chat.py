
import pytest
from factories import (
    ChannelMessageFactory,
    ChannelMemberFactory,
    DirectMessageFactory,
)


@pytest.mark.django_db
def test_create_channel_message():
    message = ChannelMessageFactory()
    assert message.pk is not None
    assert message.content

@pytest.mark.django_db
def test_direct_message_exchange():
    dm = DirectMessageFactory()
    assert dm.pk is not None
    assert dm.thread.user1 != dm.thread.user2

@pytest.mark.django_db
def test_channel_membership():
    member = ChannelMemberFactory()
    assert member.channel
    assert member.user
