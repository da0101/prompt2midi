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

inline juce::String eventPrefix (const juce::String& type)
{
    if (type == "done" || type == "complete")
        return "DONE";
    if (type == "stage")
        return "STEP";
    if (type == "warning")
        return "WARN";
    if (type == "failed")
        return "FAIL";
    return "INFO";
}

inline juce::String summarizeStatus (const juce::var& root)
{
    auto* rootObject = root.getDynamicObject();
    if (rootObject == nullptr)
        return "Waiting for backend status...";

    auto status = rootObject->getProperty ("status").toString();
    auto progress = rootObject->getProperty ("progress").toString();
    auto message = rootObject->getProperty ("message").toString();
    auto events = rootObject->getProperty ("events");

    juce::String output;
    output << "STATUS";
    if (status.isNotEmpty())
        output << ": " << status;
    if (progress.isNotEmpty())
        output << " (" << progress << "%)";
    output << "\n";
    if (message.isNotEmpty())
        output << message << "\n";

    if (auto* eventArray = events.getArray())
    {
        output << "\nPIPELINE\n";
        for (const auto& event : *eventArray)
        {
            auto* object = event.getDynamicObject();
            if (object == nullptr)
                continue;

            auto type = object->getProperty ("type").toString();
            auto label = object->getProperty ("label").toString();
            auto detail = object->getProperty ("detail").toString();

            output << eventPrefix (type) << "  " << label;
            if (detail.isNotEmpty())
                output << " - " << detail;
            output << "\n";
        }
    }
    else
    {
        output << "\nPipeline events will appear here once analysis starts.\n";
    }

    return output;
}

inline juce::String summarizeComposition (const juce::var& composition, juce::String& promptForClipboard, const juce::var& sunoPrompt)
{
    auto* compObject = composition.getDynamicObject();
    if (compObject == nullptr)
        return {};

    auto bars    = compObject->getProperty ("bars").toString();
    auto bpm     = compObject->getProperty ("bpm").toString();
    auto key     = compObject->getProperty ("key").toString();
    auto style   = compObject->getProperty ("style").toString();
    auto midi    = compObject->getProperty ("midi");
    auto desc    = compObject->getProperty ("description");

    juce::String output;
    output << "Generated Loop Package\n";
    output << "Style: "  << (style.isNotEmpty() ? style : "unknown") << "\n";
    output << "BPM: "    << (bpm.isNotEmpty()   ? bpm   : "unknown") << "\n";
    output << "Key: "    << (key.isNotEmpty()    ? key   : "unknown") << "\n";
    output << "Bars: "   << (bars.isNotEmpty()   ? bars  : "32")      << "\n\n";

    if (auto* midiObject = midi.getDynamicObject())
    {
        output << "Files:\n";
        for (const juce::String& track : { juce::String ("bass"), juce::String ("drums"),
                                           juce::String ("chords"), juce::String ("melody"),
                                           juce::String ("full_loop") })
        {
            auto filePath = midiObject->getProperty (track).toString();
            if (filePath.isNotEmpty())
                output << "  " << track << ": " << filePath << "\n";
        }
        output << "\n";
    }

    if (auto* descObject = desc.getDynamicObject())
    {
        output << "Track notes:\n";
        for (const juce::String& track : { juce::String ("bass"), juce::String ("drums"),
                                           juce::String ("chords"), juce::String ("melody") })
        {
            auto note = descObject->getProperty (track).toString();
            if (note.isNotEmpty())
                output << "  " << track << ": " << note << "\n";
        }
        output << "\n";
    }

    if (auto* sunoObject = sunoPrompt.getDynamicObject())
    {
        promptForClipboard = sunoObject->getProperty ("text").toString();
        if (promptForClipboard.isNotEmpty())
            output << "SUNO Prompt:\n" << promptForClipboard << "\n\n";
    }

    return output;
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

    auto analysis     = resultObject->getProperty ("analysis");
    auto composition  = resultObject->getProperty ("composition");
    auto sunoPrompt   = resultObject->getProperty ("suno_prompt");
    auto interpretation = resultObject->getProperty ("interpretation");
    auto midiNotes    = resultObject->getProperty ("midi_notes");

    auto bpm           = propertyString (analysis, "bpm");
    auto key           = propertyString (analysis, "key");
    auto bpmConfidence = propertyString (analysis, "bpm_confidence");
    auto keyConfidence = propertyString (analysis, "key_confidence");

    juce::String output;

    // Reference analysis header
    output << "Reference Analysis\n";
    output << "BPM: " << (bpm.isNotEmpty() ? bpm : "unknown");
    if (bpmConfidence.isNotEmpty())
        output << " (" << confidenceLabel (bpmConfidence) << " confidence)";
    output << "\n";
    output << "Key: " << (key.isNotEmpty() ? key : "unknown");
    if (keyConfidence.isNotEmpty())
        output << " (" << confidenceLabel (keyConfidence) << " confidence)";
    output << "\n\n";

    auto warnings = analysis.getDynamicObject() != nullptr
        ? analysis.getDynamicObject()->getProperty ("warnings")
        : juce::var();
    if (auto* warningArray = warnings.getArray())
    {
        for (const auto& w : *warningArray)
        {
            auto text = w.toString();
            if (text.containsIgnoreCase ("not source-track") || text.containsIgnoreCase ("rough tonal"))
                continue;
            output << "Note: " << text << "\n";
        }
        if (warningArray->size() > 0)
            output << "\n";
    }

    // Generated loop package (primary product output)
    juce::String compBlock = summarizeComposition (composition, promptForClipboard, sunoPrompt);
    if (compBlock.isNotEmpty())
    {
        output << compBlock;
    }
    else
    {
        // Fallback: show producer prompt from old path when no composition available
        auto summary = propertyString (interpretation, "producer_summary");
        auto aiPrompt = propertyString (interpretation, "ai_music_prompt");
        promptForClipboard = aiPrompt;
        output << "Producer insight:\n" << summary << "\n\n";
        output << "AI music prompt:\n" << aiPrompt << "\n\n";
    }

    if (auto* notes = midiNotes.getArray())
    {
        for (const auto& note : *notes)
            output << "Note: " << note.toString() << "\n";
    }

    return output;
}
}
