/*
  ==============================================================================

    This file contains the basic framework code for a JUCE plugin editor.

  ==============================================================================
*/

#include "PluginProcessor.h"
#include "PluginEditor.h"

//==============================================================================
Prompt2midiAudioProcessorEditor::Prompt2midiAudioProcessorEditor (Prompt2midiAudioProcessor& p)
    : AudioProcessorEditor (&p), audioProcessor (p)
{
    // Make sure that before the constructor has finished, you've set the
    // editor's size to whatever you need it to be.
    setSize (400, 300);
    
    // Setup UI Components
    promptInput.setMultiLine(true);
    promptInput.setReturnKeyStartsNewLine(true);
    promptInput.setTextToShowWhenEmpty("Enter your prompt here...", juce::Colours::grey);
    addAndMakeVisible(promptInput);
    
    generateButton.setButtonText("Generate");
    generateButton.onClick = [this]() {
        // TODO: Add ChatGPT integration here
    };
    addAndMakeVisible(generateButton);
}

Prompt2midiAudioProcessorEditor::~Prompt2midiAudioProcessorEditor()
{
}

//==============================================================================
void Prompt2midiAudioProcessorEditor::paint (juce::Graphics& g)
{
    // (Our component is opaque, so we must completely fill the background with a solid colour)
    g.fillAll (getLookAndFeel().findColour (juce::ResizableWindow::backgroundColourId));
}

void Prompt2midiAudioProcessorEditor::resized()
{
    // This is generally where you'll want to lay out the positions of any
    // subcomponents in your editor..
    
    auto bounds = getLocalBounds();
    
    // Prompt input (take most of the space)
    auto promptInputArea = bounds.removeFromTop(bounds.getHeight() - 50);
    promptInput.setBounds(promptInputArea.reduced(10, 10));
    
    // Generate button (bottom)
    generateButton.setBounds(bounds.reduced(10, 10));
}
