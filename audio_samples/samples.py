from gtts import gTTS

audio_samples = {
    "sample-recording-1-task-with-due-date-and-reminder.mp3": "Follow up with my boss, latest by August 30th, remind me August 20th. We should talk about our AI strategy!",
    "sample-recording-2-random-thoughts.mp3": "These are just some random thoughts. I need to think about that some time soon-ish",
    "sample-recording-3-send-email.mp3": "send an email to myself to remind me to find out what 42 is about",
    "sample-recording-4-tought-on-ai.mp3": "a thought on generative ai and agents: what would be criteria to shape bounded contexts for agents and when to better invoke an agent in another context e.g. with A2A",
    "sample-recording-5-tought-on-ea.mp3": "when thinking about enterprise architecture and agentic automation: is data a separate capability that is to be exposed by agents or is data included in process capabilities?",
}

for filename, text in audio_samples.items():
    tts = gTTS(text, lang="en")
    tts.save(filename)
