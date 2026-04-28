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

inline juce::String confidenceLabel (const juce::String& raw)
{
    auto value = raw.getDoubleValue();
    if (value >= 0.7)
        return raw + " high";
    if (value >= 0.4)
        return raw + " medium";
    if (value > 0.0)
        return raw + " low";
    return raw.isNotEmpty() ? raw + " unavailable" : "unavailable";
}

inline void appendStringArray (juce::String& output, const juce::var& value, const juce::String& prefix)
{
    if (auto* array = value.getArray())
        for (const auto& item : *array)
            output << prefix << item.toString() << "\n";
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
    auto midiAssets = resultObject->getProperty ("midi_assets");
    auto midiNotes = resultObject->getProperty ("midi_notes");

    auto bpm = propertyString (analysis, "bpm");
    auto key = propertyString (analysis, "key");
    auto loudness = propertyString (analysis, "loudness");
    auto bpmConfidence = propertyString (analysis, "bpm_confidence");
    auto keyConfidence = propertyString (analysis, "key_confidence");
    auto summary = propertyString (interpretation, "producer_summary");
    promptForClipboard = propertyString (interpretation, "ai_music_prompt");

    juce::String output;
    output << "BPM: " << (bpm.isNotEmpty() ? bpm : "unknown");
    if (bpmConfidence.isNotEmpty())
        output << " (" << confidenceLabel (bpmConfidence) << " confidence)";
    output << "\n";
    output << "Key: " << (key.isNotEmpty() ? key : "unknown");
    if (keyConfidence.isNotEmpty())
        output << " (" << confidenceLabel (keyConfidence) << " confidence)";
    output << "\n";
    output << "Loudness: " << (loudness.isNotEmpty() ? loudness + " dBFS" : "unknown") << "\n\n";

    auto warnings = analysis.getDynamicObject() != nullptr
        ? analysis.getDynamicObject()->getProperty ("warnings")
        : juce::var();
    appendStringArray (output, warnings, "Warning: ");
    if (warnings.getArray() != nullptr)
        output << "\n";

    output << "Producer insight:\n" << summary << "\n\n";
    output << "AI music prompt:\n" << promptForClipboard << "\n\n";

    if (auto* assets = midiAssets.getArray())
    {
        output << "MIDI assets:\n";
        for (const auto& asset : *assets)
        {
            auto* object = asset.getDynamicObject();
            if (object == nullptr)
                continue;

            auto label = object->getProperty ("label").toString();
            auto path = object->getProperty ("path").toString();
            auto confidence = object->getProperty ("confidence").toString();
            auto sourceMethod = object->getProperty ("source_method").toString();

            output << "- " << (label.isNotEmpty() ? label : "MIDI asset");
            if (confidence.isNotEmpty())
                output << " (" << confidenceLabel (confidence) << " confidence)";
            if (sourceMethod.isNotEmpty())
                output << "\n  Method: " << sourceMethod;
            if (path.isNotEmpty())
                output << "\n  " << path;
            output << "\n";
            appendStringArray (output, object->getProperty ("limitations"), "  Limitation: ");
        }
        output << "\n";
    }
    else
    {
    if (auto* midiObject = midiFiles.getDynamicObject())
    {
        auto sketchPath = midiObject->getProperty ("reference_sketch").toString();
        if (sketchPath.isNotEmpty())
            output << "MIDI reference sketch (not transcription):\n" << sketchPath << "\n";

        auto bassPath = midiObject->getProperty ("bass_transcription").toString();
        if (bassPath.isNotEmpty())
            output << "\nExperimental bass transcription:\n" << bassPath << "\n";
    }
    }

    if (auto* notes = midiNotes.getArray())
    {
        for (const auto& note : *notes)
            output << "\nNote: " << note.toString();
    }

    return output;
}
}
