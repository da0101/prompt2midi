#pragma once

#include <JuceHeader.h>

namespace prompt2midi
{
inline juce::String requestJson (const juce::String& url, const juce::String& postBody = {})
{
    juce::URL request (url);

    if (postBody.isNotEmpty())
    {
        request = request.withPOSTData (postBody);
        auto stream = request.createInputStream (
            juce::URL::InputStreamOptions (juce::URL::ParameterHandling::inPostData)
                .withConnectionTimeoutMs (3000)
                .withExtraHeaders ("Content-Type: application/json\r\n"));
        return stream != nullptr ? stream->readEntireStreamAsString() : juce::String();
    }

    auto stream = request.createInputStream (
        juce::URL::InputStreamOptions (juce::URL::ParameterHandling::inAddress)
            .withConnectionTimeoutMs (3000));
    return stream != nullptr ? stream->readEntireStreamAsString() : juce::String();
}

inline juce::String escapeJson (const juce::String& value)
{
    juce::String escaped;
    for (auto character : value)
    {
        if (character == '\\' || character == '"')
            escaped << '\\' << character;
        else if (character == '\n')
            escaped << "\\n";
        else if (character == '\r')
            escaped << "\\r";
        else if (character == '\t')
            escaped << "\\t";
        else
            escaped << character;
    }
    return escaped;
}

inline juce::String propertyString (const juce::var& object, const juce::String& name)
{
    if (auto* dynamicObject = object.getDynamicObject())
        return dynamicObject->getProperty (juce::Identifier (name)).toString();

    return {};
}

inline juce::String summarizeResult (const juce::var& root, juce::String& promptForClipboard)
{
    auto* rootObject = root.getDynamicObject();
    if (rootObject == nullptr)
        return "The backend returned an unreadable response.";

    auto result = rootObject->getProperty ("result");
    auto* resultObject = result.getDynamicObject();
    if (resultObject == nullptr)
        return "The backend returned no result object.";

    auto analysis = resultObject->getProperty ("analysis");
    auto interpretation = resultObject->getProperty ("interpretation");
    auto midiFiles = resultObject->getProperty ("midi_files");

    auto bpm = propertyString (analysis, "bpm");
    auto key = propertyString (analysis, "key");
    auto loudness = propertyString (analysis, "loudness");
    auto summary = propertyString (interpretation, "producer_summary");
    promptForClipboard = propertyString (interpretation, "ai_music_prompt");

    juce::String output;
    output << "BPM: " << (bpm.isNotEmpty() ? bpm : "unknown") << "\n";
    output << "Key: " << (key.isNotEmpty() ? key : "unknown") << "\n";
    output << "Loudness: " << (loudness.isNotEmpty() ? loudness + " dBFS" : "unknown") << "\n\n";
    output << "Producer insight:\n" << summary << "\n\n";
    output << "AI music prompt:\n" << promptForClipboard << "\n\n";

    if (auto* midiObject = midiFiles.getDynamicObject())
    {
        auto bassPath = midiObject->getProperty ("bass").toString();
        if (bassPath.isNotEmpty())
            output << "MIDI bassline:\n" << bassPath << "\n";
    }

    return output;
}
}
