"""Constants for the Schulportal Hessen integration."""

from datetime import timedelta

DOMAIN = "schulportal_hessen"

CONF_SCHOOL_ID = "school_id"
CONF_SCHOOL_NAME = "school_name"
CONF_QUERY = "query"
CONF_SCHOOL = "school"

# Coordinator runs often; each category has its own time-to-live so the portal
# is not asked for data that rarely changes.
UPDATE_INTERVAL = timedelta(minutes=30)
TTL_SUBSTITUTIONS = timedelta(minutes=25)
TTL_HOMEWORK = timedelta(hours=1)
TTL_CALENDAR = timedelta(hours=6)
TTL_TIMETABLE = timedelta(hours=12)
TTL_APPLETS = timedelta(hours=6)

# Applet names (lower case, substring match) as listed by the portal.
APPLET_SUBSTITUTIONS = "vertretungsplan"
APPLET_TIMETABLE = "stundenplan"
APPLET_CALENDAR = "kalender"
APPLET_HOMEWORK = "mein unterricht"

EVENT_NEW_HOMEWORK = f"{DOMAIN}_new_homework"
EVENT_NEW_SUBSTITUTION = f"{DOMAIN}_new_substitution"

MAX_ATTRIBUTE_ITEMS = 25
