# import datetime
import logging
import os
import webapp2
# import json
from google.appengine.ext.webapp import template
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.api import memcache


class user_profile(ndb.Model):
    user_id = ndb.StringProperty()
    name = ndb.StringProperty()
    location = ndb.StringProperty()
    interests = ndb.StringProperty()


class event_info(ndb.Model):
    title = ndb.StringProperty()
    summary = ndb.StringProperty()
    location = ndb.StringProperty()
    information = ndb.TextProperty()
    start_date = ndb.StringProperty()
    end_date = ndb.StringProperty()
    start_time = ndb.StringProperty()
    end_time = ndb.StringProperty()
    attendance = ndb.IntegerProperty()  ## assuming this is a number for now
    time_created = ndb.DateTimeProperty(auto_now_add=True)
    votes = ndb.IntegerProperty()
    # event_number = ndb.IntegerProperty()
    user = ndb.StringProperty()
    has_up_voted = ndb.StringProperty(repeated=True)
    has_down_voted = ndb.StringProperty(repeated=True)
    featured = ndb.BooleanProperty()

    def create_comment(self, xuser, xtext):
        comment = event_comment(parent=self.key)
        comment.populate(user=xuser, text=xtext)
        comment.put()
        return comment

    def get_comments(self):
        result = list()
        q = event_comment.query(ancestor=self.key)
        q = q.order(-event_comment.time_created)
        for i in q.fetch(100):
            result.append(i)
        return result

    def delete_comments(self):
        result = list()
        q = event_comment.query(ancestor=self.key)
        for i in q.fetch(100):
            i.key.delete()


class event_comment(ndb.Model):
    user = ndb.StringProperty()
    text = ndb.TextProperty()
    time_created = ndb.DateTimeProperty(auto_now_add=True)


def delete_comments(id):
    event = get_event_info(id)
    event.delete_comments()
    event.put()
    memcache.set(event.key.urlsafe(), event, namespace='event')


def setFeatured(id):
    event = get_event_info(id)
    event.featured = not event.featured
    event.put()
    memcache.set(event.key.urlsafe(), event, namespace='event')


def clearVotes(id):
    event = get_event_info(id)
    del event.has_up_voted[:]
    del event.has_down_voted[:]
    event.votes = 0;
    event.put()
    memcache.set(event.key.urlsafe(), event, namespace='event')


def create_event(title, summary, information, start_date, end_date, start_time, end_time, attendance, location, email):
    event = event_info()
    event.populate(title=title,
                   summary=summary,
                   information=information,
                   start_date=start_date,
                   end_date=end_date,
                   start_time=start_time,
                   end_time=end_time,
                   attendance=attendance,
                   location=location,
                   featured=False,
                   votes=0,
                   user=email, )
    # event_number = event_number,)

    ##event.key = ndb.Key(event_info, event_number)
    event.put()

    memcache.delete('events')
    memcache.set(event.key.urlsafe(), event, namespace='event')

    return event.key.urlsafe()


def edit_event(title, summary, information, start_date, end_date, start_time, end_time, attendance, location, id):
    event = get_event_info(id)
    event.populate(title=title,
                   summary=summary,
                   information=information,
                   start_date=start_date,
                   end_date=end_date,
                   start_time=start_time,
                   end_time=end_time,
                   attendance=attendance,
                   location=location, )

    ##event.key = ndb.Key(event_info, event_number)
    event.put()

    memcache.delete('events')
    memcache.set(event.key.urlsafe(), event, namespace='event')

    return event.key.urlsafe()


def delete_event(id):
    event = get_event_info(id)
    event.delete_comments()
    memcache.delete(id, namespace="event")
    event.key.delete()


def get_event_info(id):
    result = memcache.get(id, namespace="event")
    if not result:
        # result = ndb.Key(event_info, int(id)).get()
        key = ndb.Key(urlsafe=id)
        result = key.get()
        memcache.set(id, result, namespace='event')
    return result


def DownVoteEvent(id, email):
    event = get_event_info(id)

    if not check_if_down_voted(event.has_down_voted, email):
        event.has_down_voted.append(email)
        if check_if_up_voted(event.has_up_voted, email):
            event.has_up_voted.remove(email)

        event.votes = len(event.has_up_voted) - len(event.has_down_voted)
        if event.votes < 0:
            event.votes = 0
        event.put()
        memcache.set(id, event, namespace='event')


def UpVoteEvent(id, email):
    event = get_event_info(id)

    if not check_if_up_voted(event.has_up_voted, email):
        event.has_up_voted.append(email)
        if check_if_down_voted(event.has_down_voted, email):
            event.has_down_voted.remove(email)

        event.votes = len(event.has_up_voted) - len(event.has_down_voted)
        if event.votes < 0:
            event.votes = 0
        event.put()
        memcache.set(id, event, namespace='event')


def check_if_up_voted(has_up_voted, email):
    if email in has_up_voted:
        return True
    return False


def check_if_down_voted(has_down_voted, email):
    if email in has_down_voted:
        return True
    return False


def obtain_events():
    result = memcache.get("events")
    if not result:
        result = list()
        q = event_info.query()
        for event in q.fetch(100):
            result.append(event)
        memcache.set('events', result)
    return result


def sort_by_votes():
    result = memcache.get("sort_by_votes")
    if not result:
        result = list()
        q = event_info.query()
        q = q.order(-event_info.votes)
        for i in q.fetch(5):
            result.append(i)
        memcache.set("sort_by_votes", result)
    return result


def get_featured():
    result = memcache.get("featured")
    if not result:
        result = list()
        q = event_info.query(event_info.featured == True)
        for i in q.fetch(5):
            result.append(i)
        memcache.set("featured", result)
    return result


def get_recent_events():
    result = memcache.get("recent_events")
    if not result:
        result = list()
        q = event_info.query()
        q = q.order(-event_info.time_created)
        for i in q.fetch(5):
            result.append(i)
        memcache.set("recent_events", result)
    return result


def get_by_location(location):
    result = list()
    q = event_info.query(event_info.location == location)
    q = q.order(-event_info.time_created)
    for i in q.fetch(5):
        result.append(i)
    return result


def get_user_profile(id):
    result = memcache.get(id, namespace="profile")
    if not result:
        result = ndb.Key(user_profile, id).get()
        memcache.set(id, result, namespace="profile")
    return result


def check_if_user_profile_exists(id):
    result = list()
    q = user_profile.query(user_profile.user_id == id)
    q = q.fetch(1)

    ##if q == []:
    return q


def update_profile(id, name, location, interests):
    profile = get_user_profile(id)
    profile.populate(name=name, location=location, interests=interests)
    profile.put()
    memcache.set(id, profile, namespace="profile")


def create_profile(id):
    profile = user_profile()
    profile.user_id = id
    profile.key = ndb.Key(user_profile, id)
    profile.put()

    memcache.set(id, profile, namespace="profile")
