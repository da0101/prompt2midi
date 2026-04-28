/*
  ==============================================================================

    This file contains the basic framework code for a JUCE plugin editor.

  ==============================================================================
*/

#pragma once

#include <JuceHeader.h>
#include "PluginProcessor.h"

//==============================================================================
/**
*/
class Prompt2midiAudioProcessorEditor  : public juce::AudioProcessorEditor
{
public:
    Prompt2midiAudioProcessorEditor (Prompt2midiAudioProcessor&);
    ~Prompt2midiAudioProcessorEditor() override;

    //==============================================================================
    void paint (juce::Graphics&) override;
    void resized() override;

private:
    // This reference is provided as a quick way for your editor to
    // access the processor object that created it.
    Prompt2midiAudioProcessor& audioProcessor;
    
    // UI Components
    juce::TextEditor promptInput;
    juce::TextButton generateButton;

    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR (Prompt2midiAudioProcessorEditor)
};
