#pragma once

#include <JuceHeader.h>

namespace prompt2midi::theme
{
static const auto backgroundTop = juce::Colour (0xff101315);
static const auto backgroundBottom = juce::Colour (0xff171a20);
static const auto panel = juce::Colour (0xff1b2125);
static const auto panelRaised = juce::Colour (0xff232d31);
static const auto panelDeep = juce::Colour (0xff111719);
static const auto stroke = juce::Colour (0xff3b454b);
static const auto text = juce::Colour (0xfff4f7f5);
static const auto mutedText = juce::Colour (0xffaeb8b7);
static const auto accent = juce::Colour (0xff33e58b);
static const auto accentDark = juce::Colour (0xff1c8f5a);
static const auto cyan = juce::Colour (0xff73c7ff);

inline void drawRoundedPanel (juce::Graphics& g, juce::Rectangle<int> bounds, juce::Colour fill, juce::Colour outline)
{
    auto rect = bounds.toFloat();
    juce::DropShadow (juce::Colours::black.withAlpha (0.2f), 12, { 0, 6 }).drawForRectangle (g, bounds);
    g.setColour (fill);
    g.fillRoundedRectangle (rect, 8.0f);
    g.setColour (outline);
    g.drawRoundedRectangle (rect, 8.0f, 1.0f);
}

inline void styleActionButton (juce::TextButton& button, bool primary)
{
    button.setColour (juce::TextButton::buttonColourId, primary ? accent : panelRaised);
    button.setColour (juce::TextButton::buttonOnColourId, primary ? accent.brighter (0.08f) : panelRaised.brighter (0.1f));
    button.setColour (juce::TextButton::textColourOffId, primary ? juce::Colour (0xff07120d) : text);
    button.setColour (juce::TextButton::textColourOnId, primary ? juce::Colour (0xff07120d) : text);
}

inline void styleTextEditor (juce::TextEditor& editor)
{
    editor.setFont (juce::Font (juce::FontOptions (15.0f)));
    editor.setColour (juce::TextEditor::backgroundColourId, juce::Colours::transparentBlack);
    editor.setColour (juce::TextEditor::textColourId, text);
    editor.setColour (juce::TextEditor::highlightColourId, accent.withAlpha (0.28f));
    editor.setColour (juce::TextEditor::highlightedTextColourId, text);
    editor.setColour (juce::TextEditor::outlineColourId, juce::Colours::transparentBlack);
    editor.setColour (juce::TextEditor::focusedOutlineColourId, accent.withAlpha (0.8f));
}

class LookAndFeel final : public juce::LookAndFeel_V4
{
public:
    LookAndFeel()
    {
        setColour (juce::ScrollBar::thumbColourId, cyan.withAlpha (0.74f));
        setColour (juce::CaretComponent::caretColourId, accent);
    }

    void drawButtonBackground (juce::Graphics& g, juce::Button& button, const juce::Colour&, bool over, bool down) override
    {
        auto* textButton = dynamic_cast<juce::TextButton*> (&button);
        const auto primary = textButton != nullptr && textButton->findColour (juce::TextButton::buttonColourId) == accent;
        auto fill = primary ? accent : panel;
        if (! button.isEnabled()) fill = panel.withMultipliedAlpha (0.55f);
        else if (down) fill = fill.darker (0.12f);
        else if (over) fill = fill.brighter (0.08f);

        auto rect = button.getLocalBounds().toFloat().reduced (1.0f);
        juce::DropShadow (juce::Colours::black.withAlpha (0.2f), 8, { 0, 4 }).drawForRectangle (g, button.getLocalBounds());
        g.setColour (fill);
        g.fillRoundedRectangle (rect, 9.0f);
        g.setColour ((primary ? accent : stroke).brighter (0.2f));
        g.drawRoundedRectangle (rect, 9.0f, 1.3f);
    }
};
}
