#ifndef __QD_LOCALIZATION_H__
#define __QD_LOCALIZATION_H__

#include <string>

//! Localization settings for text and voice output.
class qdLocalization
{
public:
	enum Language {
		LANGUAGE_RUSSIAN = 0,
		LANGUAGE_ENGLISH = 1
	};

	enum VoiceMode {
		VOICE_ORIGINAL = 0,
		VOICE_TRANSLATED = 1,
		VOICE_SUBTITLES_ONLY = 2
	};

	qdLocalization();

	void load();
	void save() const;

	Language language() const { return language_; }
	VoiceMode voice_mode() const { return voice_mode_; }

	void set_language(Language language){ language_ = language; }
	void set_voice_mode(VoiceMode mode){ voice_mode_ = mode; }

	const char* language_name() const;
	const char* voice_mode_name() const;

	bool is_english() const { return language_ == LANGUAGE_ENGLISH; }
	bool use_translated_voices() const { return voice_mode_ == VOICE_TRANSLATED; }
	bool subtitles_only() const { return voice_mode_ == VOICE_SUBTITLES_ONLY; }

	std::string resolve_text_database(const char* database_path) const;
	const char* translate_resource_path(const char* path) const;

	static qdLocalization& instance();

private:
	Language language_;
	VoiceMode voice_mode_;

	static qdLocalization config_;
};

#endif // __QD_LOCALIZATION_H__