import json
import time
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import joinedload, selectinload
from app.extensions import db
from app.models.mc_script import (
    McTemplate,
    McTemplateSegment,
    McScript,
    McScriptSegment,
)
from app.models.user import User
from app.utils.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.utils.datetime_utils import utc_now


DEFAULT_EVENT_STRUCTURES: Dict[str, Dict] = {
    "Technical Talk": {
        "description": "Standard university technical expert talk, guest lecture, or chapter keynote.",
        "segments": [
            {
                "segment_type": "pre_event_announcement",
                "title": "Pre-Event Announcements & Decorum",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Ask audience to silence mobile devices, maintain decorum, and await dignitary arrival.",
                "default_stage_directions": "[MC 1 speaks with polite, audible clarity from podium; waits for room silence]",
            },
            {
                "segment_type": "opening_greeting",
                "title": "Opening Greeting & MC Introduction",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Introduce self and co-host, welcome audience on behalf of department and club/society.",
                "default_stage_directions": "[Warm smile, energetic opening posture, acknowledging the audience]",
            },
            {
                "segment_type": "dignitary_introduction",
                "title": "Dignitary Acknowledgement & Welcome",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Formally acknowledge directors, deans, HOD, branch counsellors, and coordinators (including in-absentia mentions).",
                "default_stage_directions": "[Gestures respectfully towards dignitaries seated on stage or dais]",
            },
            {
                "segment_type": "welcome_address",
                "title": "Welcome Address Invitation",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Invite Head of Department or faculty coordinator to stage for welcome address.",
                "default_stage_directions": "[Applause cue; step slightly aside as dignitary steps to podium]",
            },
            {
                "segment_type": "speaker_introduction",
                "title": "Speaker 1 Introduction & Biography",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Detailed academic background, degrees, affiliations, research accolades, awards, top 2% list, and session topic.",
                "default_stage_directions": "[Present biography with reverence; invite dignitary for sapling presentation before talk]",
            },
            {
                "segment_type": "custom",
                "title": "Technical Session 1 Delivery & Stage Cue",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Hand over microphone to Speaker 1 for lecture delivery.",
                "default_stage_directions": "[Speaker 1 delivers session; MCs seated in designated stage wing]",
            },
            {
                "segment_type": "memento_presentation",
                "title": "Speaker 1 Appreciation & Memento Presentation",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Express gratitude for session takeaways and invite dignitary to present memento.",
                "default_stage_directions": "[Lead applause; announce memento presenter on stage]",
            },
            {
                "segment_type": "speaker_introduction",
                "title": "Speaker 2 Introduction & Biography",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Introduce second technical speaker, research background, engineering career, and specialized paper/topic.",
                "default_stage_directions": "[Present bio; call student volunteer for sapling presentation]",
            },
            {
                "segment_type": "custom",
                "title": "Technical Session 2 Delivery & Stage Cue",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Invite Speaker 2 to the podium for the session.",
                "default_stage_directions": "[Speaker 2 delivers talk; MCs monitor time from tech desk]",
            },
            {
                "segment_type": "memento_presentation",
                "title": "Speaker 2 Appreciation & Memento Presentation",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Conclude technical segment, appreciate speaker, invite memento presentation.",
                "default_stage_directions": "[Lead heartfelt applause; photo opportunity on dais]",
            },
            {
                "segment_type": "vote_of_thanks",
                "title": "Vote of Thanks Invitation",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Invite faculty coordinator or branch counsellor to deliver formal vote of thanks.",
                "default_stage_directions": "[Invite faculty member to podium; applause cue]",
            },
            {
                "segment_type": "anthem_closing",
                "title": "University Anthem & Formal Standing",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Request entire assembly to rise for the University Anthem.",
                "default_stage_directions": "[Stand at strict attention as anthem plays]",
            },
            {
                "segment_type": "feedback_announcements",
                "title": "Feedback QR, Attendance & Refreshments",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Instruct students to scan on-screen QR code for certificates, announce tea/snacks and class attendance.",
                "default_stage_directions": "[Point to projector screen; announce dispersal procedure]",
            },
        ],
    },
    "Valedictory Function": {
        "description": "Annual department, hackathon, or club valedictory and leadership recognition ceremony.",
        "segments": [
            {
                "segment_type": "pre_event_announcement",
                "title": "Pre-Event Announcements & Settling In",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Polite reminder to take seats and put phones on silent mode.",
                "default_stage_directions": "[Gentle opening bell or microphone check]",
            },
            {
                "segment_type": "opening_greeting",
                "title": "Welcome & Introduction to Flagship Event",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Welcome faculty, students, guests to the Valedictory function celebrating year-long achievements.",
                "default_stage_directions": "[MC 1 and MC 2 standing side-by-side with poised enthusiasm]",
            },
            {
                "segment_type": "badge_distribution",
                "title": "Badge Distribution – Student Body Heads & Vice-Heads",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Invite faculty on stage, call each Head and Vice-Head by team/role, organize group photo.",
                "default_stage_directions": "[Call leaders one by one; request all to remain on stage for official photograph]",
            },
            {
                "segment_type": "event_report",
                "title": "Introduction & Report of the Event",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Invite Event Head to present comprehensive report of activities, efforts, and milestones.",
                "default_stage_directions": "[Invite Event Head to podium; pause for applause]",
            },
            {
                "segment_type": "custom",
                "title": "Highlights Video Showcase",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Introduce highlights and memory video capturing hard work and experiences.",
                "default_stage_directions": "[Stage lights dim; prompt AV crew to roll video]",
            },
            {
                "segment_type": "prize_distribution",
                "title": "Prize Distribution Ceremony",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Build suspense, announce competition categories, read 1st, 2nd, 3rd winners with exact names and teams.",
                "default_stage_directions": "[Call winners to stage; invite faculty to present certificates and trophies]",
            },
            {
                "segment_type": "speaker_introduction",
                "title": "Guest Address & Technical Insights",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Introduce senior dignitary/guest with career highlights, awards, and invite for valedictory address.",
                "default_stage_directions": "[Invite guest to podium; sapling presentation if scheduled]",
            },
            {
                "segment_type": "feedback_announcements",
                "title": "Feedback Form & Certificate Details",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Express gratitude to guest and request participants to fill feedback forms.",
                "default_stage_directions": "[Display feedback QR slide]",
            },
            {
                "segment_type": "anthem_closing",
                "title": "University Anthem",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Request everyone to rise in reverence for the University Anthem.",
                "default_stage_directions": "[Audience rises; anthem plays]",
            },
            {
                "segment_type": "custom",
                "title": "Conclusion & Final Thanks",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Official concluding remarks, wishing participants continued success.",
                "default_stage_directions": "[Final warm wave and stage sign-off]",
            },
        ],
    },
    "Inauguration Ceremony": {
        "description": "Formal opening ceremony for symposia, conferences, club chapters, or annual summits.",
        "segments": [
            {
                "segment_type": "pre_event_announcement",
                "title": "Pre-Event Announcements",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Request audience to silence phones, maintain silence for invocation, await dignitaries.",
                "default_stage_directions": "[Audience settling in; MC stands behind podium]",
            },
            {
                "segment_type": "opening_greeting",
                "title": "Opening Salutations & Welcome",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Extend warm greetings to distinguished gathering, introduce theme of the inaugural day.",
                "default_stage_directions": "[Confident and welcoming delivery]",
            },
            {
                "segment_type": "custom",
                "title": "Invocation & Prayer Song",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Invite university choir or student prayer group to seek divine blessings.",
                "default_stage_directions": "[Pause for choir; auditorium stands or remains silent in reverence]",
            },
            {
                "segment_type": "custom",
                "title": "Lighting of the Lamp / Formal Inauguration",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Invite dignitaries to light the ceremonial lamp, symbolizing enlightenment and innovation.",
                "default_stage_directions": "[Dignitaries step to oil lamp; traditional instrumental audio softly plays]",
            },
            {
                "segment_type": "welcome_address",
                "title": "Welcome Address by Head of Department",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Formally invite HOD to set the tone with the inaugural welcome address.",
                "default_stage_directions": "[Applause cue; welcome HOD to dais]",
            },
            {
                "segment_type": "dignitary_introduction",
                "title": "Introduction of Chief Guest & Presidential Address",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Introduce Chief Guest, career achievements, and invite to deliver the Inaugural Keynote Address.",
                "default_stage_directions": "[Dignitary sapling presentation followed by keynote invitation]",
            },
            {
                "segment_type": "event_report",
                "title": "Theme Overview & Event Launch",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Present the roadmap of competitions, tracks, or symposium timeline.",
                "default_stage_directions": "[Projector displays event poster/banner]",
            },
            {
                "segment_type": "vote_of_thanks",
                "title": "Inaugural Vote of Thanks",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Invite faculty coordinator for inaugural vote of thanks.",
                "default_stage_directions": "[Faculty takes stage; formal applause]",
            },
            {
                "segment_type": "anthem_closing",
                "title": "University Anthem",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Request assembly to rise for anthem.",
                "default_stage_directions": "[Rise for anthem; transition to first track]",
            },
        ],
    },
    "Hackathon": {
        "description": "Intensive multi-hour coding hackathon, problem statement release, and mentoring kickoff.",
        "segments": [
            {
                "segment_type": "opening_greeting",
                "title": "High-Energy Welcome & Hackathon Introduction",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Electrifying opening greeting welcoming student hackers, sponsors, and mentors.",
                "default_stage_directions": "[Upbeat energetic tempo; music fades as MC speaks]",
            },
            {
                "segment_type": "dignitary_introduction",
                "title": "Acknowledgement of Industry Mentors & Judges",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Introduce industry jury members, technical mentors, and keynote sponsors.",
                "default_stage_directions": "[Jury stands to acknowledge applause]",
            },
            {
                "segment_type": "custom",
                "title": "Problem Statement Reveal & Rules Briefing",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Walk through hackathon tracks, evaluation criteria, GitHub submission deadlines, and ethics.",
                "default_stage_directions": "[Slides advance to problem statements]",
            },
            {
                "segment_type": "custom",
                "title": "Official Hackathon Countdown & Hack Kickoff",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Lead audience in a 10-second countdown to commence the hacking sprint.",
                "default_stage_directions": "[Crowd countdown from 10 to 1; horn sounds]",
            },
            {
                "segment_type": "feedback_announcements",
                "title": "Mentorship Rounds & Food/Rest Zones Announcement",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Explain when mentors visit tables, Wi-Fi credentials, power banks, and midnight refreshments.",
                "default_stage_directions": "[Point to volunteer help-desk]",
            },
        ],
    },
    "Workshop": {
        "description": "Hands-on technical workshop or training session with live demonstrations.",
        "segments": [
            {
                "segment_type": "opening_greeting",
                "title": "Workshop Welcome & Theme Overview",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Welcome participants to practical skill-building workshop.",
                "default_stage_directions": "[Encouraging and pragmatic tone]",
            },
            {
                "segment_type": "speaker_introduction",
                "title": "Resource Person / Trainer Introduction",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Introduce expert trainer, industry credentials, and workshop agenda.",
                "default_stage_directions": "[Present sapling/welcome badge]",
            },
            {
                "segment_type": "custom",
                "title": "Hands-on Lab Kickoff & Environment Setup",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Instruct students on repo cloning, API keys, software dependencies.",
                "default_stage_directions": "[Trainer takes podium; technical staff assists rows]",
            },
            {
                "segment_type": "memento_presentation",
                "title": "Trainer Felicitation & Memento Presentation",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Acknowledge expert guidance, call faculty to hand memento.",
                "default_stage_directions": "[Warm applause; group photo with coordinators]",
            },
            {
                "segment_type": "vote_of_thanks",
                "title": "Vote of Thanks & Certificate Instructions",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Brief closing remarks, thanking participants and trainer.",
                "default_stage_directions": "[Distribute feedback form]",
            },
        ],
    },
    "Symposium": {
        "description": "Academic and engineering symposium featuring multiple tracks and paper presentations.",
        "segments": [
            {
                "segment_type": "pre_event_announcement",
                "title": "Pre-Event Housekeeping & Track Notice",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Announce track rooms, presentation time-limits, and decorum.",
                "default_stage_directions": "[Formal, structured delivery]",
            },
            {
                "segment_type": "opening_greeting",
                "title": "Inaugural Symposium Welcome",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Welcome delegates, researchers, and students to the annual symposium.",
                "default_stage_directions": "[Poised academic atmosphere]",
            },
            {
                "segment_type": "dignitary_introduction",
                "title": "Dignitary Acknowledgement",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Introduce key academic leaders and session chairs.",
                "default_stage_directions": "[Acknowledge session chairs]",
            },
            {
                "segment_type": "welcome_address",
                "title": "Symposium Convenor Welcome Address",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Invite Convenor to share symposium vision.",
                "default_stage_directions": "[Invite convenor to stage]",
            },
            {
                "segment_type": "speaker_introduction",
                "title": "Keynote Speaker Introduction",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Comprehensive academic introduction of keynote dignitary.",
                "default_stage_directions": "[Sapling presentation followed by keynote]",
            },
            {
                "segment_type": "prize_distribution",
                "title": "Best Paper & Poster Awards",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Announce best paper awards and track felicitations.",
                "default_stage_directions": "[Hand out certificates]",
            },
            {
                "segment_type": "vote_of_thanks",
                "title": "Formal Vote of Thanks",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Express gratitude to all reviewers, chairs, delegates.",
                "default_stage_directions": "[Applause cue]",
            },
            {
                "segment_type": "anthem_closing",
                "title": "University Anthem",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Request audience to rise for the anthem.",
                "default_stage_directions": "[Assembly stands]",
            },
        ],
    },
    "Conference": {
        "description": "Multi-day academic conference with peer-reviewed tracks and international keynotes.",
        "segments": [
            {
                "segment_type": "opening_greeting",
                "title": "Conference Opening Salutations",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Welcome global researchers and delegates to the conference.",
                "default_stage_directions": "[Distinguished, international conference tone]",
            },
            {
                "segment_type": "welcome_address",
                "title": "Conference General Chair Welcome",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Invite General Chair for welcoming remarks.",
                "default_stage_directions": "[Welcome chair to dais]",
            },
            {
                "segment_type": "speaker_introduction",
                "title": "Plenary Keynote Introduction",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Bio of plenary keynote scientist.",
                "default_stage_directions": "[Invite speaker to dais]",
            },
            {
                "segment_type": "memento_presentation",
                "title": "Keynote Memento Presentation",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Invite Dean to felicitate plenary speaker.",
                "default_stage_directions": "[Memento presentation and photo]",
            },
            {
                "segment_type": "vote_of_thanks",
                "title": "Conference Vote of Thanks",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Thank organizing committee and sponsors.",
                "default_stage_directions": "[Conclude session]",
            },
        ],
    },
    "Prize Distribution": {
        "description": "Dedicated award and prize distribution ceremony for sports, hackathons, or cultural fests.",
        "segments": [
            {
                "segment_type": "opening_greeting",
                "title": "Opening Greetings & Celebration Announcement",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Set a jubilant and celebratory tone honoring excellence.",
                "default_stage_directions": "[Enthusiastic and high energy]",
            },
            {
                "segment_type": "welcome_address",
                "title": "Opening Address by Jury / Faculty Head",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Invite head of jury to summarize competition evaluation.",
                "default_stage_directions": "[Invite jury representative to podium]",
            },
            {
                "segment_type": "prize_distribution",
                "title": "Award Distribution (Track by Track)",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Call winners for each category, team name, and position with exact fidelity.",
                "default_stage_directions": "[Music sting as each winner walks to stage; photo ops]",
            },
            {
                "segment_type": "custom",
                "title": "Special Recognitions & Consolation Awards",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Recognize special efforts and honorable mentions.",
                "default_stage_directions": "[Stage photo with all winners]",
            },
            {
                "segment_type": "vote_of_thanks",
                "title": "Vote of Thanks & Photo Session",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Thank judges, organizers, and congratulate all contestants.",
                "default_stage_directions": "[Group photo cue on dais]",
            },
        ],
    },
    "Department Event": {
        "description": "General departmental meeting, club orientation, faculty day, or student assembly.",
        "segments": [
            {
                "segment_type": "pre_event_announcement",
                "title": "Pre-Event Assembly & Seating",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Assemble students by class/section; maintain orderly seating.",
                "default_stage_directions": "[Audience takes designated row seats]",
            },
            {
                "segment_type": "opening_greeting",
                "title": "Department Gathering Welcome",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Welcome faculty and peers to the departmental assembly.",
                "default_stage_directions": "[Warm departmental camaraderie]",
            },
            {
                "segment_type": "welcome_address",
                "title": "Head of Department Address",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Invite HOD to share department updates and student achievements.",
                "default_stage_directions": "[HOD takes podium; attentive silence]",
            },
            {
                "segment_type": "event_report",
                "title": "Club Activities & Semester Plan",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Present upcoming competitions, VAC courses, and initiatives.",
                "default_stage_directions": "[Slides advance to calendar of events]",
            },
            {
                "segment_type": "vote_of_thanks",
                "title": "Vote of Thanks",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Thank faculty mentors and student coordinators.",
                "default_stage_directions": "[Applause cue]",
            },
        ],
    },
    "Cultural Event": {
        "description": "Department cultural fest, talent showcase, musical evening, or festive celebration.",
        "segments": [
            {
                "segment_type": "opening_greeting",
                "title": "Vibrant Cultural Welcome",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Lively, celebratory opening capturing cultural vibrancy and festive spirit.",
                "default_stage_directions": "[Bright stage illumination; upbeat stage presence]",
            },
            {
                "segment_type": "custom",
                "title": "Inaugural Performance / Dance",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Introduce opening classical or fusion dance troupe.",
                "default_stage_directions": "[MC steps off dais; stage lighting transitions]",
            },
            {
                "segment_type": "custom",
                "title": "Musical & Stage Performances",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Introduce music band, solo acts, and drama performances.",
                "default_stage_directions": "[Dynamic banter between MC 1 and MC 2]",
            },
            {
                "segment_type": "prize_distribution",
                "title": "Cultural Awards & Trophies",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Announce best performer, best team, and overall champions.",
                "default_stage_directions": "[Trophies handed over with loud cheering]",
            },
            {
                "segment_type": "anthem_closing",
                "title": "National / University Anthem",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Respectfully conclude cultural fest with the anthem.",
                "default_stage_directions": "[Rise in unity for anthem]",
            },
        ],
    },
    "Guest Lecture": {
        "description": "Distinguished expert guest lecture or industry professional session.",
        "segments": [
            {
                "segment_type": "opening_greeting",
                "title": "Welcome to Guest Lecture Series",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Introduce the lecture theme and welcome students.",
                "default_stage_directions": "[Attentive and focused tone]",
            },
            {
                "segment_type": "speaker_introduction",
                "title": "Distinguished Guest Introduction & Bio",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Detailed career biography, industry leadership, topic summary.",
                "default_stage_directions": "[Sapling presentation before session]",
            },
            {
                "segment_type": "custom",
                "title": "Lecture Delivery & Q&A Facilitation",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Invite questions from student audience following talk.",
                "default_stage_directions": "[Pass microphones among student rows]",
            },
            {
                "segment_type": "memento_presentation",
                "title": "Token of Reverence & Memento",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Invite senior faculty to present memento.",
                "default_stage_directions": "[Handover memento; applause]",
            },
            {
                "segment_type": "vote_of_thanks",
                "title": "Vote of Thanks & Feedback Form",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Formal thank you and feedback instruction.",
                "default_stage_directions": "[Close session]",
            },
        ],
    },
    "Seminar": {
        "description": "Technical seminar session with interactive discussion and research analysis.",
        "segments": [
            {
                "segment_type": "opening_greeting",
                "title": "Seminar Opening Salutation",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Welcome participants to the research seminar.",
                "default_stage_directions": "[Professional academic atmosphere]",
            },
            {
                "segment_type": "speaker_introduction",
                "title": "Seminar Lead & Topic Introduction",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Introduce seminar moderator and key themes.",
                "default_stage_directions": "[Invite speaker to dais]",
            },
            {
                "segment_type": "custom",
                "title": "Interactive Open Floor Discussion",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Moderate discussion points and time limits.",
                "default_stage_directions": "[Facilitate audience interaction]",
            },
            {
                "segment_type": "vote_of_thanks",
                "title": "Vote of Thanks",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Acknowledge participants and concluding thoughts.",
                "default_stage_directions": "[Formal applause]",
            },
        ],
    },
    "Competition": {
        "description": "Student competition (quiz, debate, circuit design, coding challenge).",
        "segments": [
            {
                "segment_type": "opening_greeting",
                "title": "Welcome to the Competition Arena",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Enthusiastic welcome encouraging competitive excellence.",
                "default_stage_directions": "[High enthusiasm and energy]",
            },
            {
                "segment_type": "dignitary_introduction",
                "title": "Jury Introduction & Guidelines",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Introduce judges and outline rules, rounds, and negative marking.",
                "default_stage_directions": "[Judges nod from jury bench]",
            },
            {
                "segment_type": "custom",
                "title": "Competition Rounds & Live Moderation",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Call teams and manage round transitions.",
                "default_stage_directions": "[Keep rounds on strict schedule]",
            },
            {
                "segment_type": "prize_distribution",
                "title": "Final Results & Winner Felicitation",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Announce top 3 winners with fanfare.",
                "default_stage_directions": "[Trophy and certificate presentation]",
            },
        ],
    },
    "Orientation Programme": {
        "description": "Freshers orientation, club induction, and introduction to campus resources.",
        "segments": [
            {
                "segment_type": "opening_greeting",
                "title": "Warm Welcome to the New Batch",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Warm, inspiring greeting welcoming freshers to the department family.",
                "default_stage_directions": "[Warm and encouraging demeanor]",
            },
            {
                "segment_type": "welcome_address",
                "title": "Dean / Director Welcome Address",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Invite dean to address incoming students.",
                "default_stage_directions": "[Invite dignitary to stage]",
            },
            {
                "segment_type": "event_report",
                "title": "Club Journey, Wings & Community Overview",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Introduce CUESTIC wings: Media, Documentation, Volunteering, MC, Technical.",
                "default_stage_directions": "[Roll club intro slide deck]",
            },
            {
                "segment_type": "custom",
                "title": "Icebreaker & Senior-Junior Interaction",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Encourage participation and campus exploration.",
                "default_stage_directions": "[Interactive audience questions]",
            },
            {
                "segment_type": "anthem_closing",
                "title": "University Anthem",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Conclude orientation with university anthem.",
                "default_stage_directions": "[All rise for anthem]",
            },
        ],
    },
    "Custom Event": {
        "description": "Completely customizable programme sequence for unique department events.",
        "segments": [
            {
                "segment_type": "opening_greeting",
                "title": "Opening Greetings",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Welcome guests and introduce event purpose.",
                "default_stage_directions": "[Stage opening]",
            },
            {
                "segment_type": "dignitary_introduction",
                "title": "Dignitary Acknowledgement",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Acknowledge respected guests on dais.",
                "default_stage_directions": "[Dais acknowledgement]",
            },
            {
                "segment_type": "custom",
                "title": "Main Event Proceedings",
                "default_mc_assignment": "MC 1",
                "ai_instructions": "Execute primary event activity.",
                "default_stage_directions": "[Main stage activity]",
            },
            {
                "segment_type": "vote_of_thanks",
                "title": "Vote of Thanks & Closing",
                "default_mc_assignment": "MC 2",
                "ai_instructions": "Conclude event and express gratitude.",
                "default_stage_directions": "[Formal closing]",
            },
        ],
    },
}


class McTemplateService:
    """Service managing reusable MC Script Templates and Programme Blueprints."""

    _TEMPLATES_CACHE: Dict[str, Tuple[float, List[Dict]]] = {}
    _CATALOG_CACHE: Optional[List[Dict]] = None
    _CACHE_TTL = 300  # 5 minutes

    @classmethod
    def seed_default_templates(cls):
        """Idempotently ensure all 15 default event templates are available in DB."""
        seeded_count = McTemplate.query.filter_by(is_default=True).count()
        if seeded_count >= len(DEFAULT_EVENT_STRUCTURES):
            return

        for event_type, data in DEFAULT_EVENT_STRUCTURES.items():
            existing = McTemplate.query.filter_by(event_type=event_type, is_default=True).first()
            if not existing:
                template = McTemplate(
                    name=f"Standard {event_type} Template",
                    event_type=event_type,
                    description=data["description"],
                    is_public_to_team=True,
                    is_default=True,
                )
                db.session.add(template)
                db.session.flush()

                for order, seg in enumerate(data["segments"], start=1):
                    t_seg = McTemplateSegment(
                        template_id=template.id,
                        segment_type=seg["segment_type"],
                        title=seg["title"],
                        sequence_order=order,
                        default_mc_assignment=seg.get("default_mc_assignment", "MC 1"),
                        ai_instructions=seg.get("ai_instructions"),
                        default_stage_directions=seg.get("default_stage_directions"),
                    )
                    db.session.add(t_seg)
        db.session.commit()
        cls._TEMPLATES_CACHE.clear()

    @classmethod
    def list_templates(cls, user: User, event_type: Optional[str] = None) -> List[Dict]:
        """List templates accessible to the user (defaults + team public + user created) with sub-ms in-memory caching."""
        now_ts = time.time()
        cache_key = f"{user.id}_{event_type.strip() if event_type else 'all'}"
        cached = cls._TEMPLATES_CACHE.get(cache_key)
        if cached and (now_ts - cached[0] < cls._CACHE_TTL):
            return cached[1]

        query = McTemplate.query.options(
            joinedload(McTemplate.creator),
            selectinload(McTemplate.segments),
        )

        if event_type and event_type.strip():
            query = query.filter_by(event_type=event_type.strip())

        # Public to team OR created by user
        query = query.filter(
            db.or_(
                McTemplate.is_default == True,
                McTemplate.is_public_to_team == True,
                McTemplate.created_by == user.id,
            )
        ).order_by(McTemplate.is_default.desc(), McTemplate.name.asc())

        templates = query.all()
        res = [t.to_dict(include_segments=False) for t in templates]
        cls._TEMPLATES_CACHE[cache_key] = (now_ts, res)
        return res

    @classmethod
    def get_template(cls, template_id: int, user: User) -> Dict:
        """Get template with full ordered segments."""
        template = (
            McTemplate.query.options(
                joinedload(McTemplate.creator),
                selectinload(McTemplate.segments),
            )
            .filter_by(id=template_id)
            .first()
        )
        if not template:
            raise NotFoundError(f"Template with ID {template_id} not found.")
        return template.to_dict(include_segments=True)

    @classmethod
    def create_template(cls, data: Dict, user: User) -> Dict:
        """Create a new reusable MC programme template."""
        name = (data.get("name") or "").strip()
        event_type = (data.get("event_type") or "Department Event").strip()
        description = data.get("description")
        is_public = data.get("is_public_to_team", True)
        segments_data = data.get("segments") or []

        if not name:
            raise ValidationError("Template name is required.", details={"name": ["Required"]})

        template = McTemplate(
            name=name,
            event_type=event_type,
            description=description,
            created_by=user.id,
            is_public_to_team=bool(is_public),
            is_default=False,
        )
        db.session.add(template)
        db.session.flush()

        for idx, seg in enumerate(segments_data, start=1):
            t_seg = McTemplateSegment(
                template_id=template.id,
                segment_type=seg.get("segment_type", "custom"),
                title=seg.get("title", f"Segment {idx}"),
                sequence_order=idx,
                default_mc_assignment=seg.get("default_mc_assignment", "MC 1"),
                ai_instructions=seg.get("ai_instructions"),
                default_stage_directions=seg.get("default_stage_directions"),
            )
            db.session.add(t_seg)

        db.session.commit()
        cls._TEMPLATES_CACHE.clear()
        return template.to_dict(include_segments=True)

    @classmethod
    def update_template(cls, template_id: int, data: Dict, user: User) -> Dict:
        """Update a user-created template."""
        template = McTemplate.query.get(template_id)
        if not template:
            raise NotFoundError(f"Template with ID {template_id} not found.")

        if template.is_default and user.role not in ("admin", "president"):
            raise PermissionDeniedError("Default templates cannot be modified directly. Save a copy instead.")

        if data.get("name"):
            template.name = data["name"].strip()
        if "description" in data:
            template.description = data["description"]
        if data.get("event_type"):
            template.event_type = data["event_type"].strip()
        if "is_public_to_team" in data:
            template.is_public_to_team = bool(data["is_public_to_team"])

        if "segments" in data and isinstance(data["segments"], list):
            # Replace segments with updated list
            McTemplateSegment.query.filter_by(template_id=template.id).delete()
            for idx, seg in enumerate(data["segments"], start=1):
                t_seg = McTemplateSegment(
                    template_id=template.id,
                    segment_type=seg.get("segment_type", "custom"),
                    title=seg.get("title", f"Segment {idx}"),
                    sequence_order=idx,
                    default_mc_assignment=seg.get("default_mc_assignment", "MC 1"),
                    ai_instructions=seg.get("ai_instructions"),
                    default_stage_directions=seg.get("default_stage_directions"),
                )
                db.session.add(t_seg)

        template.updated_at = utc_now()
        db.session.commit()
        cls._TEMPLATES_CACHE.clear()
        return template.to_dict(include_segments=True)

    @classmethod
    def delete_template(cls, template_id: int, user: User):
        """Delete template (protected if default)."""
        template = McTemplate.query.get(template_id)
        if not template:
            raise NotFoundError(f"Template with ID {template_id} not found.")

        if template.is_default and user.role not in ("admin", "president"):
            raise PermissionDeniedError("Cannot delete system default templates.")

        if template.created_by != user.id and user.role not in ("admin", "president"):
            raise PermissionDeniedError("You do not have permission to delete this template.")

        db.session.delete(template)
        db.session.commit()
        cls._TEMPLATES_CACHE.clear()

    @classmethod
    def save_script_as_template(cls, script_id: int, template_name: str, description: Optional[str], user: User) -> Dict:
        """Create a clean reusable template from an existing script's programme structure."""
        script = McScript.query.get(script_id)
        if not script:
            raise NotFoundError(f"Script with ID {script_id} not found.")

        template = McTemplate(
            name=template_name.strip(),
            event_type=script.event_type or "Department Event",
            description=description or f"Template saved from script '{script.title}'",
            created_by=user.id,
            is_public_to_team=True,
            is_default=False,
        )
        db.session.add(template)
        db.session.flush()

        segments = script.script_segments if script.script_segments else []
        if not segments:
            # Fallback to segments_json
            legacy = script.get_segments()
            for idx, s in enumerate(legacy, start=1):
                t_seg = McTemplateSegment(
                    template_id=template.id,
                    segment_type=s.get("segment_type", "custom"),
                    title=s.get("title", f"Segment {idx}"),
                    sequence_order=idx,
                    default_mc_assignment=s.get("assigned_mc") or s.get("anchor") or "MC 1",
                    default_stage_directions=s.get("stage_direction") or s.get("stage_directions"),
                )
                db.session.add(t_seg)
        else:
            for idx, s in enumerate(segments, start=1):
                t_seg = McTemplateSegment(
                    template_id=template.id,
                    segment_type=s.segment_type,
                    title=s.title,
                    sequence_order=idx,
                    default_mc_assignment=s.assigned_mc,
                    default_stage_directions=s.stage_directions,
                )
                db.session.add(t_seg)

        db.session.commit()
        cls._TEMPLATES_CACHE.clear()
        return template.to_dict(include_segments=True)

    @classmethod
    def get_event_types_catalog(cls) -> List[Dict]:
        """Return the 15 event types with their metadata and suggested segment counts (cached)."""
        if cls._CATALOG_CACHE is not None:
            return cls._CATALOG_CACHE

        catalog = []
        for event_type, info in DEFAULT_EVENT_STRUCTURES.items():
            catalog.append({
                "event_type": event_type,
                "description": info["description"],
                "suggested_segment_count": len(info["segments"]),
                "suggested_segments": [
                    {
                        "segment_type": s["segment_type"],
                        "title": s["title"],
                        "default_mc_assignment": s["default_mc_assignment"],
                    }
                    for s in info["segments"]
                ],
            })
        cls._CATALOG_CACHE = catalog
        return catalog
