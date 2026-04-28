/*
  ==============================================================================

    Ableton-facing editor for the prompt2midi local co-producer.

  ==============================================================================
*/

#pragma once

#include <JuceHeader.h>
#include <atomic>
#include <thread>
#include "PluginProcessor.h"
#include "ModernTheme.h"

//==============================================================================
class Prompt2midiAudioProcessorEditor  : public juce::AudioProcessorEditor,
                                         public juce::FileDragAndDropTarget
{
public:
    Prompt2midiAudioProcessorEditor (Prompt2midiAudioProcessor&);
    ~Prompt2midiAudioProcessorEditor() override;

    //==============================================================================
    void paint (juce::Graphics&) override;
    void resized() override;

    bool isInterestedInFileDrag (const juce::StringArray& files) override;
    void filesDropped (const juce::StringArray& files, int x, int y) override;

private:
    void chooseAudioFile();
    void startAnalyzeJob();
    void runAnalyzeJob (juce::String prompt, juce::String audioPath);
    void configureInterface();
    void publishStatus (const juce::String& text);
    void publishResult (const juce::String& responseJson);
    void publishFailure (const juce::String& text);

    Prompt2midiAudioProcessor& audioProcessor;

    juce::Label titleLabel;
    juce::Label subtitleLabel;
    juce::Label fileLabel;
    juce::Label fileCaptionLabel;
    juce::Label promptCaptionLabel;
    juce::Label resultCaptionLabel;
    juce::TextEditor promptInput;
    juce::TextButton chooseFileButton;
    juce::TextButton analyzeButton;
    juce::TextButton copyPromptButton;
    juce::Label statusLabel;
    juce::TextEditor resultOutput;
    prompt2midi::theme::LookAndFeel modernLookAndFeel;

    std::unique_ptr<juce::FileChooser> fileChooser;
    juce::File selectedAudioFile;
    juce::String latestPrompt;
    std::thread requestThread;
    std::atomic_bool shuttingDown { false };

    static constexpr const char* localApiBase = "http://127.0.0.1:47321";

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (Prompt2midiAudioProcessorEditor)
};
