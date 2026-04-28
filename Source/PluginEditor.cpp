#include "PluginProcessor.h"
#include "PluginEditor.h"
#include "LocalApiClient.h"
Prompt2midiAudioProcessorEditor::Prompt2midiAudioProcessorEditor (Prompt2midiAudioProcessor& p)
    : AudioProcessorEditor (&p), audioProcessor (p)
{
    setSize (920, 640);
    configureInterface();
}
void Prompt2midiAudioProcessorEditor::configureInterface()
{
    setOpaque (true);
    setLookAndFeel (&modernLookAndFeel);

    titleLabel.setText ("prompt2midi", juce::dontSendNotification);
    titleLabel.setFont (juce::Font (juce::FontOptions (32.0f).withStyle ("Bold")));
    titleLabel.setColour (juce::Label::textColourId, prompt2midi::theme::text);
    addAndMakeVisible (titleLabel);
    subtitleLabel.setText ("Reference intelligence for producer prompts and MIDI sketch export", juce::dontSendNotification);
    subtitleLabel.setFont (juce::Font (juce::FontOptions (14.0f)));
    subtitleLabel.setColour (juce::Label::textColourId, prompt2midi::theme::mutedText);
    addAndMakeVisible (subtitleLabel);

    fileCaptionLabel.setText ("REFERENCE", juce::dontSendNotification);
    fileCaptionLabel.setColour (juce::Label::textColourId, prompt2midi::theme::cyan);
    fileCaptionLabel.setFont (juce::Font (juce::FontOptions (12.0f).withStyle ("Bold")));
    addAndMakeVisible (fileCaptionLabel);

    fileLabel.setText ("Drop a WAV/MP3 reference, choose one, or run prompt-only mode.", juce::dontSendNotification);
    fileLabel.setFont (juce::Font (juce::FontOptions (16.0f).withStyle ("Bold")));
    fileLabel.setColour (juce::Label::textColourId, prompt2midi::theme::text);
    addAndMakeVisible (fileLabel);
    chooseFileButton.setButtonText ("Choose Audio");
    prompt2midi::theme::styleActionButton (chooseFileButton, false);
    chooseFileButton.onClick = [this] { chooseAudioFile(); };
    addAndMakeVisible (chooseFileButton);

    promptCaptionLabel.setText ("DIRECTION", juce::dontSendNotification);
    promptCaptionLabel.setColour (juce::Label::textColourId, prompt2midi::theme::cyan);
    promptCaptionLabel.setFont (juce::Font (juce::FontOptions (12.0f).withStyle ("Bold")));
    addAndMakeVisible (promptCaptionLabel);

    promptInput.setMultiLine (true);
    promptInput.setReturnKeyStartsNewLine (true);
    promptInput.setTextToShowWhenEmpty ("Describe the track or production direction: dark groovy tech house at 124 BPM in A minor...", juce::Colours::grey);
    prompt2midi::theme::styleTextEditor (promptInput);
    addAndMakeVisible (promptInput);
    analyzeButton.setButtonText ("Analyze");
    prompt2midi::theme::styleActionButton (analyzeButton, true);
    analyzeButton.onClick = [this] { startAnalyzeJob(); };
    addAndMakeVisible (analyzeButton);

    copyPromptButton.setButtonText ("Copy Prompt");
    copyPromptButton.setEnabled (false);
    prompt2midi::theme::styleActionButton (copyPromptButton, false);
    copyPromptButton.onClick = [this] {
        if (latestPrompt.isNotEmpty())
            juce::SystemClipboard::copyTextToClipboard (latestPrompt);
    };
    addAndMakeVisible (copyPromptButton);

    statusLabel.setText ("Backend: 127.0.0.1:47321  |  Start with npm start", juce::dontSendNotification);
    statusLabel.setFont (juce::Font (juce::FontOptions (14.0f).withStyle ("Bold")));
    statusLabel.setColour (juce::Label::textColourId, prompt2midi::theme::mutedText);
    statusLabel.setJustificationType (juce::Justification::centredLeft);
    addAndMakeVisible (statusLabel);
    resultCaptionLabel.setText ("OUTPUT", juce::dontSendNotification);
    resultCaptionLabel.setColour (juce::Label::textColourId, prompt2midi::theme::cyan);
    resultCaptionLabel.setFont (juce::Font (juce::FontOptions (12.0f).withStyle ("Bold")));
    addAndMakeVisible (resultCaptionLabel);

    resultOutput.setMultiLine (true);
    resultOutput.setReadOnly (true);
    resultOutput.setScrollbarsShown (true);
    resultOutput.setTextToShowWhenEmpty ("Analysis results will appear here.", juce::Colours::grey);
    prompt2midi::theme::styleTextEditor (resultOutput);
    addAndMakeVisible (resultOutput);
}

Prompt2midiAudioProcessorEditor::~Prompt2midiAudioProcessorEditor()
{
    shuttingDown = true;
    setLookAndFeel (nullptr);
    if (requestThread.joinable())
        requestThread.join();
}

void Prompt2midiAudioProcessorEditor::paint (juce::Graphics& g)
{
    juce::ColourGradient background (prompt2midi::theme::backgroundTop, 0.0f, 0.0f,
                                     prompt2midi::theme::backgroundBottom, 0.0f, (float) getHeight(), false);
    background.addColour (0.55, juce::Colour (0xff141a18));
    g.setGradientFill (background);
    g.fillAll();

    auto bounds = getLocalBounds().reduced (24);
    bounds.removeFromTop (76);

    auto filePanel = bounds.removeFromTop (104);
    prompt2midi::theme::drawRoundedPanel (g, filePanel, prompt2midi::theme::panel,
                                           selectedAudioFile.existsAsFile() ? prompt2midi::theme::accentDark : prompt2midi::theme::stroke);

    bounds.removeFromTop (14);
    auto promptPanel = bounds.removeFromTop (150);
    prompt2midi::theme::drawRoundedPanel (g, promptPanel, prompt2midi::theme::panelRaised, prompt2midi::theme::stroke);

    bounds.removeFromTop (16);
    auto actions = bounds.removeFromTop (50);
    auto status = actions.removeFromRight (390).reduced (0, 3);
    prompt2midi::theme::drawRoundedPanel (g, status, prompt2midi::theme::panelDeep, prompt2midi::theme::accent.withAlpha (0.35f));

    bounds.removeFromTop (16);
    prompt2midi::theme::drawRoundedPanel (g, bounds, prompt2midi::theme::panelRaised, prompt2midi::theme::stroke);
}

void Prompt2midiAudioProcessorEditor::resized()
{
    auto bounds = getLocalBounds().reduced (24);

    auto header = bounds.removeFromTop (76);
    titleLabel.setBounds (header.removeFromTop (40));
    subtitleLabel.setBounds (header);

    auto filePanel = bounds.removeFromTop (104).reduced (22, 16);
    chooseFileButton.setBounds (filePanel.removeFromRight (150).withSizeKeepingCentre (150, 46));
    filePanel.removeFromRight (18);
    fileCaptionLabel.setBounds (filePanel.removeFromTop (22));
    fileLabel.setBounds (filePanel);

    bounds.removeFromTop (14);
    auto promptPanel = bounds.removeFromTop (150).reduced (18, 12);
    promptCaptionLabel.setBounds (promptPanel.removeFromTop (22));
    promptInput.setBounds (promptPanel);

    bounds.removeFromTop (16);
    auto actions = bounds.removeFromTop (50);
    analyzeButton.setBounds (actions.removeFromLeft (150).reduced (0, 2));
    actions.removeFromLeft (12);
    copyPromptButton.setBounds (actions.removeFromLeft (150).reduced (0, 2));
    statusLabel.setBounds (actions.removeFromRight (390).reduced (18, 0));

    bounds.removeFromTop (16);
    auto resultPanel = bounds.reduced (18, 12);
    resultCaptionLabel.setBounds (resultPanel.removeFromTop (22));
    resultOutput.setBounds (resultPanel);
}

bool Prompt2midiAudioProcessorEditor::isInterestedInFileDrag (const juce::StringArray& files)
{
    for (const auto& path : files)
    {
        auto file = juce::File (path);
        if (file.hasFileExtension ("wav;wave;mp3"))
            return true;
    }

    return false;
}

void Prompt2midiAudioProcessorEditor::filesDropped (const juce::StringArray& files, int, int)
{
    for (const auto& path : files)
    {
        auto file = juce::File (path);
        if (file.hasFileExtension ("wav;wave;mp3"))
        {
            selectedAudioFile = file;
            fileLabel.setText ("Reference loaded: " + file.getFileName(), juce::dontSendNotification);
            repaint();
            return;
        }
    }
}

void Prompt2midiAudioProcessorEditor::chooseAudioFile()
{
    fileChooser = std::make_unique<juce::FileChooser> ("Choose an audio file to analyze", juce::File{}, "*.wav;*.wave;*.mp3");
    fileChooser->launchAsync (juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectFiles,
                              [this] (const juce::FileChooser& chooser)
                              {
                                  auto file = chooser.getResult();
                                  if (file.existsAsFile())
                                  {
                                      selectedAudioFile = file;
                                      fileLabel.setText ("Reference loaded: " + file.getFileName(), juce::dontSendNotification);
                                      repaint();
                                  }
                              });
}

void Prompt2midiAudioProcessorEditor::startAnalyzeJob()
{
    if (requestThread.joinable())
        requestThread.join();

    latestPrompt.clear();
    resultOutput.clear();
    copyPromptButton.setEnabled (false);
    analyzeButton.setEnabled (false);
    publishStatus ("Submitting local job...");

    auto prompt = promptInput.getText();
    auto audioPath = selectedAudioFile.existsAsFile() ? selectedAudioFile.getFullPathName() : juce::String();

    requestThread = std::thread ([this, prompt, audioPath]
    {
        runAnalyzeJob (prompt, audioPath);
    });
}

void Prompt2midiAudioProcessorEditor::runAnalyzeJob (juce::String prompt, juce::String audioPath)
{
    auto body = juce::String ("{\"prompt\":\"") + prompt2midi::escapeJson (prompt) + "\",\"audioPath\":\"" + prompt2midi::escapeJson (audioPath) + "\"}";
    auto startResponse = prompt2midi::requestJson (juce::String (localApiBase) + "/analyze", body);
    auto startJson = juce::JSON::parse (startResponse);
    auto jobId = prompt2midi::propertyString (startJson, "job_id");

    if (jobId.isEmpty())
    {
        publishFailure ("Could not start analysis. Is the local backend running?");
        return;
    }

    for (int attempt = 0; attempt < 240 && ! shuttingDown; ++attempt)
    {
        juce::Thread::sleep (500);
        auto statusUrl = juce::String (localApiBase) + "/status?id=" + juce::URL::addEscapeChars (jobId, true);
        auto statusResponse = prompt2midi::requestJson (statusUrl);
        auto statusJson = juce::JSON::parse (statusResponse);
        auto status = prompt2midi::propertyString (statusJson, "status");
        auto message = prompt2midi::propertyString (statusJson, "message");

        if (message.isNotEmpty())
            publishStatus (message);

        if (status == "succeeded")
        {
            auto resultUrl = juce::String (localApiBase) + "/result?id=" + juce::URL::addEscapeChars (jobId, true);
            publishResult (prompt2midi::requestJson (resultUrl));
            return;
        }

        if (status == "failed")
        {
            publishFailure ("Analysis failed. Check the backend terminal for details.");
            return;
        }
    }

    publishFailure ("Analysis timed out.");
}

void Prompt2midiAudioProcessorEditor::publishStatus (const juce::String& text)
{
    juce::Component::SafePointer<Prompt2midiAudioProcessorEditor> safeThis (this);
    juce::MessageManager::callAsync ([safeThis, text]
    {
        if (safeThis != nullptr)
            safeThis->statusLabel.setText (text, juce::dontSendNotification);
    });
}

void Prompt2midiAudioProcessorEditor::publishResult (const juce::String& responseJson)
{
    juce::Component::SafePointer<Prompt2midiAudioProcessorEditor> safeThis (this);
    juce::MessageManager::callAsync ([safeThis, responseJson]
    {
        if (safeThis == nullptr)
            return;

        juce::String promptForClipboard;
        auto summary = prompt2midi::summarizeResult (juce::JSON::parse (responseJson), promptForClipboard);
        safeThis->latestPrompt = promptForClipboard;
        safeThis->resultOutput.setText (summary, juce::dontSendNotification);
        safeThis->copyPromptButton.setEnabled (promptForClipboard.isNotEmpty());
        safeThis->analyzeButton.setEnabled (true);
        safeThis->statusLabel.setText ("Analysis complete.", juce::dontSendNotification);
    });
}

void Prompt2midiAudioProcessorEditor::publishFailure (const juce::String& text)
{
    juce::Component::SafePointer<Prompt2midiAudioProcessorEditor> safeThis (this);
    juce::MessageManager::callAsync ([safeThis, text]
    {
        if (safeThis == nullptr)
            return;

        safeThis->statusLabel.setText (text, juce::dontSendNotification);
        safeThis->analyzeButton.setEnabled (true);
    });
}
