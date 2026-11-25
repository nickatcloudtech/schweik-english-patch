/* ---------------------------- INCLUDE SECTION ----------------------------- */

#include "qd_precomp.h"

#include "qd_localization.h"
#include "qd_setup.h"

/* ----------------------------- STRUCT SECTION ----------------------------- */
/* ----------------------------- EXTERN SECTION ----------------------------- */
/* --------------------------- PROTOTYPE SECTION ---------------------------- */
/* --------------------------- DEFINITION SECTION --------------------------- */

qdLocalization qdLocalization::config_;

qdLocalization::qdLocalization()
: language_(LANGUAGE_ENGLISH)
, voice_mode_(VOICE_ORIGINAL)
{
}

qdLocalization& qdLocalization::instance()
{
	return config_;
}

void qdLocalization::load()
{
	const char* p = getIniKey(qdGameConfig::ini_name(), "localization", "language");
	if(strlen(p)){
		if(!stricmp(p, "russian"))
			language_ = LANGUAGE_RUSSIAN;
		else if(!stricmp(p, "english"))
			language_ = LANGUAGE_ENGLISH;
	}

	p = getIniKey(qdGameConfig::ini_name(), "localization", "voice_mode");
	if(strlen(p)){
		if(!stricmp(p, "original"))
			voice_mode_ = VOICE_ORIGINAL;
		else if(!stricmp(p, "translated"))
			voice_mode_ = VOICE_TRANSLATED;
		else if(!stricmp(p, "subtitles_only"))
			voice_mode_ = VOICE_SUBTITLES_ONLY;
	}
}

void qdLocalization::save() const
{
	putIniKey(qdGameConfig::ini_name(), "localization", "language", language_name());
	putIniKey(qdGameConfig::ini_name(), "localization", "voice_mode", voice_mode_name());
}

const char* qdLocalization::language_name() const
{
	switch(language_){
	case LANGUAGE_RUSSIAN:
		return "russian";
	case LANGUAGE_ENGLISH:
	default:
		return "english";
	}
}

const char* qdLocalization::voice_mode_name() const
{
	switch(voice_mode_){
	case VOICE_ORIGINAL:
		return "original";
	case VOICE_TRANSLATED:
		return "translated";
	case VOICE_SUBTITLES_ONLY:
		return "subtitles_only";
	default:
		return "original";
	}
}

std::string qdLocalization::resolve_text_database(const char* database_path) const
{
	if(!database_path || !*database_path || language_ == LANGUAGE_RUSSIAN)
		return database_path ? database_path : "";

	std::string english_path = database_path;
	std::string::size_type slash_pos = english_path.find_last_of("\\/");
	std::string::size_type dot_pos = english_path.find_last_of('.');

	if(dot_pos == std::string::npos || (slash_pos != std::string::npos && dot_pos < slash_pos)){
		english_path += "_en";
	}
	else {
		english_path.insert(dot_pos, "_en");
	}

	if(app_io::is_file_exist(english_path.c_str()))
		return english_path;

	return database_path;
}

const char* qdLocalization::translate_resource_path(const char* path) const
{
	static std::string translated_path;
	static std::string source_marker = "Resource\\Voices\\";
	static std::string target_marker = "Resource\\Voices_en\\";

	if(!path || !*path || voice_mode_ != VOICE_TRANSLATED)
		return path;

	translated_path = path;
	std::string::size_type pos = translated_path.find(source_marker);
	if(pos != std::string::npos){
		translated_path.replace(pos, source_marker.size(), target_marker);
		return translated_path.c_str();
	}

	pos = translated_path.find("Resource/Voices/");
	if(pos != std::string::npos){
		translated_path.replace(pos, 16, "Resource/Voices_en/");
		return translated_path.c_str();
	}

	return path;
}