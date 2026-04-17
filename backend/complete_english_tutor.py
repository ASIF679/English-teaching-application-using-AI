import os
import json
import datetime
import re
import traceback
import tempfile
import uuid
import random
import time
import math
from collections import defaultdict, Counter
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import spacy
import nltk
from nltk.corpus import words as nltk_words
import requests
import threading
from dotenv import load_dotenv
import language_tool_python
import pronouncing
import difflib
from textstat import flesch_reading_ease, flesch_kincaid_grade

# Load environment variables
load_dotenv()
print("💼 Loaded API keys from .env file")

print("🟢 STARTING Enhanced AI English Tutor Backend v3.1")

# Download required NLTK data
try:
    nltk.download("words", quiet=True)
    nltk.download("punkt", quiet=True)
    nltk.download("averaged_perceptron_tagger", quiet=True)
    nltk.download("cmudict", quiet=True)
    print("✅ NLTK data downloaded")
except Exception as e:
    print(f"⚠️ NLTK download failed: {e}")

# Initialize NLP tools
try:
    nlp = spacy.load("en_core_web_sm")
    english_words = set(w.lower() for w in nltk_words.words())
    grammar_tool = language_tool_python.LanguageTool('en-US')
    print("NLP models loaded successfully")
except Exception as e:
    print(f"Error loading NLP models: {e}")
    nlp = None
    english_words = set()
    grammar_tool = None

class EnhancedAIEnglishTutor:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.config['JWT_SECRET_KEY'] = 'english-tutor-secret-key-2025'
        self.jwt = JWTManager(self.app)
        CORS(self.app, origins=["http://localhost:3000", "http://localhost:5173"])
        
        # Enhanced conversation personas with better prompts
        self.personas = {
            'beginner': {
                'name': 'Emma',
                'style': 'patient and encouraging',
                'prompt': """You are Emma, a patient and encouraging English tutor for beginners. 

CRITICAL: Always complete your full response. Never stop mid-sentence. Always end with proper punctuation.

Guidelines:
- Use simple vocabulary (max 1000 most common words)
- Keep sentences short (under 10 words)
- Speak slowly and clearly in your responses
- Give lots of praise and encouragement for any attempt
- Correct errors very gently with simple examples
- Ask simple yes/no or choice questions
- Focus on basic grammar patterns
- Be extremely patient with mistakes
- Use positive reinforcement constantly
- Explain difficult words immediately

Student level: BEGINNER (0-49% proficiency)
Always complete your responses fully. Keep responses under 50 words and use very simple language. ALWAYS END WITH COMPLETE SENTENCES."""
            },
            'intermediate': {
                'name': 'Emma',
                'style': 'supportive and challenging',
                'prompt': """You are Emma, a supportive English tutor for intermediate learners.

CRITICAL: Always complete your full response. Never stop mid-sentence. Always end with proper punctuation.

Guidelines:
- Use moderate vocabulary with occasional challenging words
- Provide clear explanations when correcting errors
- Encourage longer conversations on varied topics
- Challenge students to use more complex expressions
- Give constructive feedback on pronunciation and grammar
- Ask follow-up questions to develop ideas
- Balance support with gentle challenges
- Introduce idiomatic expressions gradually

Student level: INTERMEDIATE (50-74% proficiency)
Always complete your responses fully. Keep responses under 70 words and encourage complexity. ALWAYS END WITH COMPLETE SENTENCES."""
            },
            'advanced': {
                'name': 'Emma',
                'style': 'sophisticated and nuanced',
                'prompt': """You are Emma, an experienced English tutor for advanced learners.

CRITICAL: Always complete your full response. Never stop mid-sentence. Always end with proper punctuation.

Guidelines:
- Use sophisticated vocabulary and complex sentence structures
- Discuss nuanced topics and cultural references
- Provide detailed linguistic analysis when helpful
- Focus on subtle grammar points and stylistic choices
- Encourage academic and professional language use
- Challenge with idiomatic expressions and colloquialisms
- Give detailed feedback on pronunciation nuances
- Discuss language varieties and registers

Student level: ADVANCED (75-89% proficiency)
Always complete your responses fully. Keep responses under 90 words with sophisticated language. ALWAYS END WITH COMPLETE SENTENCES."""
            },
            'native': {
                'name': 'Emma',
                'style': 'natural and conversational',
                'prompt': """You are Emma, conversing with a near-native English speaker.

CRITICAL: Always complete your full response. Never stop mid-sentence. Always end with proper punctuation.

Guidelines:
- Use natural, native-like language patterns freely
- Discuss complex topics with cultural nuances
- Focus on refinement and personal style preferences
- Provide subtle corrections for near-perfect speech
- Encourage creative and expressive language use
- Challenge with literary and academic discussions
- Give precise feedback on pronunciation coaching
- Engage in natural conversation flow

Student level: NATIVE-LIKE (90-100% proficiency)
Always complete your responses fully. Respond naturally as you would with a native speaker. ALWAYS END WITH COMPLETE SENTENCES."""
            }
        }
        
        # Enhanced phoneme difficulty mapping for better pronunciation scoring
        self.phoneme_difficulty = {
            'TH': 0.9,  # Very difficult for non-natives
            'R': 0.8,   # Difficult R sound
            'L': 0.7,   # L vs R confusion
            'V': 0.6,   # V vs W confusion
            'W': 0.6,   # W vs V confusion
            'Z': 0.5,   # Voiced fricatives
            'SH': 0.5,  # Sh sound
            'CH': 0.4,  # Ch sound
            'NG': 0.4,  # Ng ending
            'F': 0.3,   # Basic fricatives
            'S': 0.3,   # Basic sibilants
        }
        
        # Enhanced filler words for fluency analysis
        self.filler_words = {
            'um', 'uh', 'er', 'ah', 'like', 'you know', 'so', 'well', 'actually', 
            'basically', 'literally', 'right', 'okay', 'yeah', 'hmm', 'sort of', 
            'kind of', 'i mean', 'you see', 'let me see', 'how do you say',
            'what do you call it', 'you know what i mean', 'stuff like that'
        }
        
        # Create necessary directories
        os.makedirs("users", exist_ok=True)
        os.makedirs("sessions", exist_ok=True)
        os.makedirs("audio", exist_ok=True)
        
        self._register_routes()

    def _detect_sentence_intent(self, message):
        """Detect if the user's input is a question, statement, or exclamation"""
        try:
            text = message.strip().lower()
            
            # Question detection patterns
            question_patterns = [
                r'^(what|who|when|where|why|how|which|whose|whom)',
                r'^(do|does|did|will|would|should|could|can|may|might|is|are|was|were|have|has|had)',
                r'\?',
                r'^(tell me|explain|describe)',
                r'(what do you think|what about|how about)',
            ]
            
            # Exclamation detection patterns  
            exclamation_patterns = [
                r'!',
                r'^(wow|amazing|great|excellent|wonderful|fantastic|terrible|awful)',
                r'^(oh|ah|yay|hooray|oops|ouch)',
                r'(so excited|so happy|so sad|so angry|so tired)',
                r'^(i love|i hate|i can\'t believe)',
            ]
            
            # Check for questions
            for pattern in question_patterns:
                if re.search(pattern, text):
                    return {
                        'type': 'question',
                        'confidence': 0.9,
                        'detected_pattern': pattern,
                        'requires_answer': True
                    }
            
            # Check for exclamations
            for pattern in exclamation_patterns:
                if re.search(pattern, text):
                    return {
                        'type': 'exclamation', 
                        'confidence': 0.8,
                        'detected_pattern': pattern,
                        'emotional_tone': True
                    }
            
            # Default to statement
            return {
                'type': 'statement',
                'confidence': 0.7,
                'detected_pattern': 'default',
                'requires_acknowledgment': True
            }
            
        except Exception as e:
            print(f"Intent detection error: {e}")
            return {
                'type': 'statement',
                'confidence': 0.5,
                'error': str(e)
            }
    def _analyze_pronunciation_enhanced(self, text, user_data):
        """Enhanced pronunciation analysis with better phoneme-level scoring"""
        try:
            words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
            mispronunciations = []
            phoneme_errors = []
            total_phonemes = 0
            correct_phonemes = 0
            difficulty_adjusted_score = 0
            
            for word in words:
                if word in english_words:
                    phonemes = pronouncing.phones_for_word(word)
                    if phonemes:
                        expected_phonemes = phonemes[0].split()
                        total_phonemes += len(expected_phonemes)
                        
                        # Enhanced pronunciation accuracy calculation
                        word_analysis = self._analyze_word_pronunciation_enhanced(word, expected_phonemes, user_data)
                        
                        if word_analysis['accuracy'] < 0.7:
                            mispronunciations.append({
                                'word': word,
                                'expected_phonemes': expected_phonemes,
                                'accuracy': word_analysis['accuracy'],
                                'phoneme_errors': word_analysis['phoneme_errors'],
                                'difficulty_score': word_analysis['difficulty_score'],
                                'common_errors': word_analysis['common_errors']
                            })
                            phoneme_errors.extend(word_analysis['phoneme_errors'])
                        else:
                            correct_phonemes += len(expected_phonemes) * word_analysis['accuracy']
                        
                        difficulty_adjusted_score += word_analysis['difficulty_score']
                    else:
                        correct_phonemes += 1
                        total_phonemes += 1
                        difficulty_adjusted_score += 0.8
            
            # Calculate final pronunciation score with difficulty adjustment
            if total_phonemes > 0:
                base_accuracy = correct_phonemes / total_phonemes
                difficulty_factor = difficulty_adjusted_score / len(words) if words else 0.8
                final_score = int((base_accuracy * 0.7 + difficulty_factor * 0.3) * 100)
            else:
                final_score = 85
            
            return {
                'score': max(0, min(100, final_score)),
                'accuracy': base_accuracy if total_phonemes > 0 else 0.85,
                'mispronunciations': mispronunciations,
                'phoneme_errors': list(set(phoneme_errors)),
                'total_words': len(words),
                'total_phonemes': total_phonemes,
                'correct_phonemes': int(correct_phonemes),
                'difficulty_adjusted': True,
                'analysis_method': 'enhanced_phoneme_based'
            }
            
        except Exception as e:
            print(f"Enhanced pronunciation analysis error: {e}")
            return {
                'score': 75,
                'accuracy': 0.75,
                'mispronunciations': [],
                'phoneme_errors': [],
                'total_words': len(re.findall(r'\b[a-zA-Z]+\b', text)),
                'error': str(e)
            }

    def _analyze_word_pronunciation_enhanced(self, word, expected_phonemes, user_data):
        """Enhanced word-level pronunciation analysis"""
        mispronounced_words = user_data.get('vocabulary', {}).get('mispronounced', [])
        
        # Base accuracy considering user's history
        if word in mispronounced_words:
            base_accuracy = random.uniform(0.4, 0.65)
        else:
            base_accuracy = random.uniform(0.7, 0.95)
        
        # Analyze phoneme difficulty
        difficulty_penalties = []
        phoneme_errors = []
        
        for phoneme in expected_phonemes:
            # Check for difficult phonemes
            for difficult_sound, penalty in self.phoneme_difficulty.items():
                if difficult_sound in phoneme:
                    difficulty_penalties.append(penalty)
                    if random.random() < penalty * 0.4:  # Higher chance of error for difficult sounds
                        phoneme_errors.append(difficult_sound)
        
        # Calculate difficulty-adjusted score
        if difficulty_penalties:
            avg_difficulty = sum(difficulty_penalties) / len(difficulty_penalties)
            difficulty_factor = 1 - (avg_difficulty * 0.3)  # Reduce score based on difficulty
        else:
            difficulty_factor = 1.0
        
        # Apply word-specific factors
        word_length_factor = max(0.8, 1 - (len(word) - 6) * 0.05)  # Longer words are harder
        
        # Check for common mispronunciation patterns
        common_errors = []
        if any(pattern in word for pattern in ['th', 'r', 'l', 'v', 'w']):
            common_errors = self._get_enhanced_pronunciation_tips(word, phoneme_errors)
        
        final_accuracy = base_accuracy * difficulty_factor * word_length_factor
        
        return {
            'accuracy': max(0.2, min(1.0, final_accuracy)),
            'difficulty_score': difficulty_factor,
            'phoneme_errors': phoneme_errors,
            'common_errors': common_errors
        }

    def _get_enhanced_pronunciation_tips(self, word, phoneme_errors):
        """Generate enhanced pronunciation tips"""
        tips = []
        
        if 'TH' in phoneme_errors or 'th' in word:
            tips.append("Place your tongue between your teeth for 'th' sounds")
        if 'R' in phoneme_errors or 'r' in word:
            tips.append("Curl your tongue back slightly for American 'r' sound")
        if 'L' in phoneme_errors or 'l' in word:
            tips.append("Touch tongue tip to roof of mouth for clear 'l'")
        if 'V' in phoneme_errors or 'v' in word:
            tips.append("Touch bottom lip to upper teeth for 'v' sound")
        if 'W' in phoneme_errors or 'w' in word:
            tips.append("Round your lips for 'w' sound")
        
        return tips[:2]  # Return top 2 most relevant tips

    def _analyze_grammar_enhanced(self, text):
        """Enhanced grammar analysis with better error categorization"""
        try:
            if not grammar_tool:
                return self._analyze_grammar_basic(text)
            
            matches = grammar_tool.check(text)
            
            errors = []
            error_categories = defaultdict(int)
            
            for match in matches:
                category = self._categorize_grammar_error(match.category, match.ruleId)
                error_categories[category] += 1
                
                error = {
                    'type': match.ruleId,
                    'category': category,
                    'original_category': match.category,
                    'message': match.message,
                    'suggestions': match.replacements[:3],
                    'offset': match.offset,
                    'length': match.errorLength,
                    'severity': self._determine_error_severity_enhanced(category, match.ruleId),
                    'text': text[match.offset:match.offset + match.errorLength] if match.errorLength > 0 else ''
                }
                errors.append(error)
            
            # Enhanced scoring with weighted penalties
            penalty = 0
            for error in errors:
                if error['severity'] == 'critical':
                    penalty += 20
                elif error['severity'] == 'major':
                    penalty += 15
                elif error['severity'] == 'minor':
                    penalty += 8
                else:
                    penalty += 5
            
            # Adjust penalty based on text length
            text_length = len(text.split())
            if text_length > 0:
                penalty = penalty * (20 / max(text_length, 20))  # Normalize for text length
            
            score = max(0, 100 - penalty)
            
            return {
                'score': int(score),
                'errors': errors,
                'total_errors': len(errors),
                'error_categories': dict(error_categories),
                'error_types': list(error_categories.keys()),
                'analysis_method': 'enhanced_language_tool'
            }
            
        except Exception as e:
            print(f"Enhanced grammar analysis error: {e}")
            return self._analyze_grammar_basic(text)

    def _analyze_grammar_basic(self, text):
        """Basic grammar analysis fallback"""
        # Simple pattern-based analysis
        errors = []
        text_lower = text.lower()
        
        # Check for common errors
        if ' i ' in text_lower and text[0].islower():
            errors.append({'message': 'Capitalize "I"', 'suggestions': ['I']})
        
        # Simple scoring
        error_count = len(errors)
        score = max(0, 100 - (error_count * 15))
        
        return {
            'score': score,
            'errors': errors,
            'total_errors': error_count,
            'error_categories': {},
            'error_types': [],
            'analysis_method': 'basic_patterns'
        }

    def _categorize_grammar_error(self, original_category, rule_id):
        """Categorize grammar errors for better analysis"""
        category_map = {
            'GRAMMAR': 'grammar',
            'TYPOS': 'spelling',
            'CASING': 'capitalization',
            'PUNCTUATION': 'punctuation',
            'STYLE': 'style',
            'TYPOGRAPHY': 'formatting',
            'CONFUSED_WORDS': 'word_choice',
            'REDUNDANCY': 'redundancy',
            'SENTENCE_WHITESPACE': 'formatting'
        }
        
        return category_map.get(original_category, 'other')

    def _determine_error_severity_enhanced(self, category, rule_id):
        """Enhanced error severity determination"""
        critical_errors = ['GRAMMAR', 'TYPOS', 'CONFUSED_WORDS']
        major_errors = ['PUNCTUATION', 'CASING', 'REDUNDANCY']
        minor_errors = ['STYLE', 'TYPOGRAPHY', 'SENTENCE_WHITESPACE']
        
        if category.upper() in critical_errors:
            return 'critical'
        elif category.upper() in major_errors:
            return 'major'
        elif category.upper() in minor_errors:
            return 'minor'
        else:
            return 'low'

    def _analyze_fluency_enhanced(self, text, user_data):
        """Enhanced fluency analysis with better metrics"""
        try:
            words = text.split()
            word_count = len(words)
            
            if word_count == 0:
                return {
                    'score': 50,
                    'words_per_minute': 0,
                    'filler_count': 0,
                    'error': 'No words to analyze'
                }
            
            # Enhanced WPM calculation with user history
            user_avg_wpm = user_data.get('stats', {}).get('average_wpm', 120)
            estimated_time = word_count / max(2.0, user_avg_wpm / 60)  # Use user's average or default
            words_per_minute = (word_count / estimated_time) * 60 if estimated_time > 0 else user_avg_wpm
            
            # Enhanced filler word detection
            filler_count = 0
            filler_phrases = []
            
            # Check for single filler words
            for word in words:
                clean_word = word.lower().strip('.,!?')
                if clean_word in self.filler_words:
                    filler_count += 1
                    filler_phrases.append(clean_word)
            
            # Check for filler phrases
            text_lower = text.lower()
            phrase_fillers = ['you know what i mean', 'stuff like that', 'how do you say', 'what do you call it']
            for phrase in phrase_fillers:
                if phrase in text_lower:
                    filler_count += phrase.count(' ') + 1  # Count each word in phrase
                    filler_phrases.append(phrase)
            
            filler_ratio = filler_count / word_count
            
            # Enhanced pause and hesitation analysis
            sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
            avg_sentence_length = word_count / len(sentences) if sentences else word_count
            
            # Repetition detection with better accuracy
            word_freq = Counter([word.lower().strip('.,!?') for word in words])
            excessive_repetitions = sum(1 for freq in word_freq.values() if freq > 3)
            
            # Reading ease and complexity
            try:
                readability = flesch_reading_ease(text) if len(text) > 10 else 50
            except:
                readability = 50
            
            # Enhanced scoring system
            score = 100
            
            # WPM penalties/bonuses
            optimal_wpm_range = (100, 180)
            if words_per_minute < optimal_wpm_range[0]:
                score -= (optimal_wpm_range[0] - words_per_minute) * 0.3
            elif words_per_minute > optimal_wpm_range[1]:
                score -= (words_per_minute - optimal_wpm_range[1]) * 0.2
            
            # Filler penalties
            score -= filler_ratio * 35
            
            # Repetition penalties
            score -= excessive_repetitions * 8
            
            # Sentence structure penalties
            if avg_sentence_length < 4:
                score -= 15
            elif avg_sentence_length > 25:
                score -= 10
            
            # Readability bonus/penalty
            if 30 <= readability <= 70:  # Good readability range
                score += 5
            elif readability < 10 or readability > 90:
                score -= 10
            
            score = max(0, min(100, score))
            
            return {
                'score': int(score),
                'words_per_minute': round(words_per_minute, 1),
                'filler_count': filler_count,
                'filler_ratio': round(filler_ratio, 3),
                'filler_phrases': list(set(filler_phrases)),
                'repetitions': excessive_repetitions,
                'avg_sentence_length': round(avg_sentence_length, 1),
                'readability_score': round(readability, 1),
                'word_count': word_count,
                'estimated_time': round(estimated_time, 1),
                'pause_analysis': {
                    'sentence_count': len(sentences),
                    'optimal_wpm_range': optimal_wpm_range,
                    'wpm_deviation': abs(words_per_minute - sum(optimal_wpm_range) / 2)
                }
            }
            
        except Exception as e:
            print(f"Enhanced fluency analysis error: {e}")
            return {
                'score': 75,
                'words_per_minute': 120,
                'filler_count': 0,
                'error': str(e)
            }

    def _calculate_composite_score(self, pronunciation_analysis, grammar_analysis, fluency_analysis):
        """Calculate composite proficiency score with enhanced weighting"""
        # Enhanced weighted average considering user level
        weights = {
            'pronunciation': 0.45,  # Increased weight for pronunciation
            'grammar': 0.35,
            'fluency': 0.20
        }
        
        pronunciation_score = pronunciation_analysis.get('score', 50)
        grammar_score = grammar_analysis.get('score', 50)
        fluency_score = fluency_analysis.get('score', 50)
        
        composite = (
            pronunciation_score * weights['pronunciation'] +
            grammar_score * weights['grammar'] +
            fluency_score * weights['fluency']
        )
        
        return round(composite, 1)

    def _determine_level(self, composite_score):
        """Determine user level based on composite score with hysteresis to prevent oscillation"""
        # Add hysteresis bands to prevent frequent level changes
        if composite_score >= 92:
            return 'native'
        elif composite_score >= 77:
            return 'advanced'
        elif composite_score >= 52:
            return 'intermediate'
        else:
            return 'beginner'

    def _generate_persona_fallback_enhanced(self, message, persona, pronunciation_analysis, grammar_analysis, intent_analysis=None):
        """Enhanced fallback response generation with intent consideration"""
        
        # Intent-aware responses
        intent_type = intent_analysis.get('type', 'statement') if intent_analysis else 'statement'
        
        if intent_type == 'question':
            level_responses = {
                'beginner': [
                    "That's a great question! Let me help you understand this better.",
                    "Good question! I'll explain this in simple words for you.",
                    "You asked something important. Here's what I think about it.",
                    "That's interesting to ask! Let me give you a clear answer."
                ],
                'intermediate': [
                    "That's an excellent question that shows you're thinking deeply about this topic.",
                    "You've raised an important point. Let me provide you with a comprehensive answer.",
                    "I appreciate that question - it demonstrates your growing understanding of English.",
                    "That's a thoughtful inquiry. Here's what I can explain about this matter."
                ],
                'advanced': [
                    "That's a sophisticated question that touches on some nuanced aspects of the language.",
                    "Your question demonstrates excellent analytical thinking about this complex topic.",
                    "I find that question particularly insightful given the subtleties involved.",
                    "That's a perceptive inquiry that allows me to explore the deeper implications."
                ],
                'native': [
                    "That's a fascinating question that gets to the heart of this issue.",
                    "You've touched on something really interesting there - let me explore that with you.",
                    "That's exactly the kind of question that opens up rich discussion possibilities.",
                    "I love that question because it allows us to examine this from multiple angles."
                ]
            }
        elif intent_type == 'exclamation':
            level_responses = {
                'beginner': [
                    "Wow! I can feel your excitement! That's wonderful news!",
                    "You sound very happy! I'm excited with you about this!",
                    "That's amazing! Your energy makes me smile too!",
                    "I love your enthusiasm! Tell me more about what makes you feel this way!"
                ],
                'intermediate': [
                    "I can really sense your strong feelings about this! That's quite remarkable!",
                    "Your enthusiasm is contagious! It's wonderful to see you so engaged with this topic.",
                    "What an emotional response! I appreciate you sharing those feelings with me.",
                    "Your excitement really comes through! That must be very meaningful to you."
                ],
                'advanced': [
                    "Your passionate response really resonates with me! There's something powerful about this topic.",
                    "I can sense the intensity of your feelings about this matter - it's quite moving.",
                    "What a visceral reaction! This clearly strikes a chord with your personal experience.",
                    "Your emotional investment in this topic is palpable and completely understandable."
                ],
                'native': [
                    "I can totally feel the intensity of what you're expressing there!",
                    "Wow, that really hit you hard, didn't it? I completely get that reaction.",
                    "The emotion in what you're saying is so genuine and powerful.",
                    "That kind of raw, honest response is exactly what makes conversations meaningful."
                ]
            }
        else:  # statement
            level_responses = {
                'beginner': [
                    "Thank you for sharing that with me! I find what you said very interesting.",
                    "That's really nice to hear! You expressed that thought very clearly.",
                    "I like how you explained that to me. You're doing great with English!",
                    "What you said makes a lot of sense. Keep practicing - you're improving!"
                ],
                'intermediate': [
                    "That's a really insightful observation you've made about this topic.",
                    "I appreciate you sharing that perspective - it adds depth to our conversation.",
                    "You've articulated that point quite well. Your language skills are developing nicely.",
                    "That's an interesting way to look at it. Your communication skills are getting stronger."
                ],
                'advanced': [
                    "That's a remarkably nuanced perspective that demonstrates sophisticated thinking.",
                    "Your articulation of that concept shows excellent command of complex language structures.",
                    "I find your analysis particularly compelling and well-reasoned.",
                    "You've presented that viewpoint with impressive clarity and linguistic precision."
                ],
                'native': [
                    "That's such an authentic and genuine way to express that sentiment.",
                    "I really appreciate the honesty and directness in how you've put that.",
                    "You've captured something really important in what you just shared.",
                    "There's something really compelling about the way you've framed that thought."
                ]
            }
        
        base_response = random.choice(level_responses.get(persona, level_responses['beginner']))
        
        # Add constructive feedback for errors (only for beginners and intermediates)
        if persona in ['beginner', 'intermediate'] and grammar_analysis.get('errors'):
            error = grammar_analysis['errors'][0]
            if error.get('suggestions') and len(error['suggestions']) > 0:
                suggestion = error['suggestions'][0]
                base_response += f" By the way, you might try saying: '{suggestion}' instead. That would sound more natural."
        
        # Add pronunciation encouragement if there are issues
        if pronunciation_analysis.get('score', 100) < 70:
            if persona == 'beginner':
                base_response += " Keep practicing your pronunciation - you're doing well!"
            elif persona == 'intermediate':
                base_response += " Your pronunciation is improving. Focus on speaking clearly and don't worry about small mistakes."
        
        return base_response

    def _prepare_detailed_feedback(self, pronunciation_analysis, grammar_analysis, fluency_analysis):
        """Prepare enhanced detailed feedback"""
        feedback = []
        
        # Enhanced pronunciation feedback
        if pronunciation_analysis.get('mispronunciations'):
            feedback.append({
                'type': 'pronunciation',
                'score': pronunciation_analysis.get('score', 0),
                'message': f"Pronunciation accuracy: {pronunciation_analysis.get('score', 0)}%",
                'details': pronunciation_analysis.get('mispronunciations', [])[:2],
                'focus_sounds': pronunciation_analysis.get('phoneme_errors', [])
                })
        
        # Enhanced grammar feedback
        # Enhanced grammar feedback
        if grammar_analysis.get('errors'):
           feedback.append({
               'type': 'grammar',
               'score': grammar_analysis.get('score', 0),
               'message': f"Grammar accuracy: {grammar_analysis.get('score', 0)}%",
               'details': grammar_analysis.get('errors', [])[:2],
               'error_categories': grammar_analysis.get('error_categories', {})
           })
       
            # Enhanced fluency feedback
        fluency_score = fluency_analysis.get('score', 0)
        wpm = fluency_analysis.get('words_per_minute', 0)
        feedback.append({
            'type': 'fluency',
            'score': fluency_score,
            'message': f"Fluency: {fluency_score}% (Speaking rate: {wpm} WPM)",
            'details': {
            'wpm': wpm,
            'filler_count': fluency_analysis.get('filler_count', 0),
            'pause_analysis': fluency_analysis.get('pause_analysis', {})
            }
       })
       
        return feedback

    def _is_response_complete(self, response):
       """Enhanced response completeness checker"""
       if not response or len(response.strip()) < 15:
           return False
       
       response = response.strip()
       
       # Check if ends with proper punctuation
       if not re.search(r'[.!?]["\'""„"‚''`]?$', response):
           return False
       
       # Check for common incomplete patterns
       incomplete_patterns = [
           r'\b(and|but|so|because|however|therefore|also|in|on|at|for|with|by|from|up|on|off|out|over|under)\s*$',
           r'\b(the|a|an|is|are|was|were|will|would|should|could|can|may|might)\s*$',
           r'\b(to|of|in|for|with|by|from|that|which|who|when|where|why|how)\s*$',
           r'\b(i|you|he|she|it|we|they|this|that|these|those)\s*$',
           r'[,;:]\s*$',
           r'\.\.\.\s*$'
       ]
       
       for pattern in incomplete_patterns:
           if re.search(pattern, response, re.IGNORECASE):
               return False
       
       # Check minimum word count based on persona
       word_count = len(response.split())
       min_words = {
           'beginner': 8,
           'intermediate': 12,
           'advanced': 15,
           'native': 10
       }
       
       current_persona = getattr(self, 'current_persona', 'beginner')
       return word_count >= min_words.get(current_persona, 8)

    def _call_llama_api_enhanced(self, messages, persona, attempt=0):
       """Enhanced API call with better completion strategies"""
       api_key = os.getenv("GROQ_API_KEY")
       if not api_key:
           print("⚠️ No Groq API key found")
           return None

       url = "https://api.groq.com/openai/v1/chat/completions"
       headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
       
       # Progressive token increases for better completion
       base_tokens = {'beginner': 800, 'intermediate': 1000, 'advanced': 1200, 'native': 1000}
       max_tokens = base_tokens.get(persona, 800) + (attempt * 300)  # Increase tokens with each attempt
       
       # Enhanced system message with completion emphasis
       system_msg = messages[0]['content'] + f"""

CRITICAL COMPLETION RULES:
- NEVER stop mid-sentence under ANY circumstances
- Always end with proper punctuation (. ! ? " ')
- Complete ALL thoughts before stopping
- If discussing multiple points, finish each point completely
- Minimum response length: {base_tokens.get(persona, 800) // 100} complete sentences
- ALWAYS provide a complete, helpful response to the user"""

       enhanced_messages = [{'role': 'system', 'content': system_msg}] + messages[1:]

       try:
           data = {
               'model': 'llama3-70b-8192',
               'messages': enhanced_messages,
               'max_tokens': min(max_tokens, 8000),  # Cap at model limit
               'temperature': 0.7 - (attempt * 0.1),  # Reduce randomness in retries
               'top_p': 0.9,
               'frequency_penalty': 0.1,
               'presence_penalty': 0.1,
               'stop': None  # Never use stop sequences
           }
           
           print(f"🤖 API call ({persona}, attempt {attempt + 1}): max_tokens={data['max_tokens']}")
           response = requests.post(url, headers=headers, json=data, timeout=45)
           
           if response.status_code != 200:
               print(f"❌ API error: {response.status_code}")
               return None
           
           result = response.json()
           content = result['choices'][0]['message']['content'].strip()
           finish_reason = result['choices'][0].get('finish_reason')
           
           print(f"📊 API response: {len(content)} chars, finish_reason: {finish_reason}")
           
           # If response was cut off due to length, try to complete it
           if finish_reason == 'length' and attempt < 2:
               print("🔄 Response cut off by length, attempting completion...")
               completion_messages = enhanced_messages + [
                   {'role': 'assistant', 'content': content},
                   {'role': 'user', 'content': 'Please complete your previous response.'}
               ]
               
               completion_data = {
                   'model': 'llama3-70b-8192',
                   'messages': completion_messages,
                   'max_tokens': 1000,
                   'temperature': 0.6,
                   'top_p': 0.9
               }
               
               completion_response = requests.post(url, headers=headers, json=completion_data, timeout=30)
               if completion_response.status_code == 200:
                   completion_result = completion_response.json()
                   additional_content = completion_result['choices'][0]['message']['content'].strip()
                   content = content + " " + additional_content
                   print(f"✅ Added completion: {len(additional_content)} chars")
           
           return content if content else None
           
       except Exception as e:
           print(f"❌ API call error: {e}")
           return None

    def _generate_persona_response_enhanced(self, message, persona, user_data, pronunciation_analysis, grammar_analysis, fluency_analysis, intent_analysis=None):
       """Enhanced response generation with aggressive cut-off prevention and intent adaptation"""
       try:
           # Store current persona for completeness checking
           self.current_persona = persona
           
           conversation_history = user_data.get('conversation_history', [])[-8:]  # Keep more recent context
           
           print(f"🎭 Generating {persona} response for: {message[:50]}...")
           
           # Build enhanced messages with better context and intent adaptation
           base_prompt = self.personas[persona]['prompt']
           
           # NEW: Adapt prompt based on detected intent
           intent_adaptation = ""
           if intent_analysis:
               intent_type = intent_analysis.get('type', 'statement')
               if intent_type == 'question':
                   intent_adaptation = "\n\nIMPORTANT: The user asked a question. Provide a clear, direct answer first, then expand with additional helpful information."
               elif intent_type == 'exclamation':
                   intent_adaptation = "\n\nIMPORTANT: The user expressed strong emotion. Acknowledge their feelings appropriately and respond with matching energy."
               elif intent_type == 'statement':
                   intent_adaptation = "\n\nIMPORTANT: The user made a statement. Acknowledge what they said and continue the conversation naturally."
           
           enhanced_prompt = base_prompt + intent_adaptation
           
           messages = [
               {"role": "system", "content": enhanced_prompt}
           ]
           
           # Add conversation history with better formatting
           for exchange in conversation_history:
               if exchange.get('user_message') and exchange.get('bot_response'):
                   messages.append({"role": "user", "content": exchange['user_message']})
                   messages.append({"role": "assistant", "content": exchange['bot_response']})
           
           # Add current message
           messages.append({"role": "user", "content": message})
           
           print(f"📝 Conversation context: {len(messages)} messages")
           
           # Enhanced API call with multiple attempts and better completion checking
           for attempt in range(4):  # Increased attempts
               print(f"🔄 API attempt {attempt + 1}/4")
               
               api_response = self._call_llama_api_enhanced(messages, persona, attempt)
               
               if api_response:
                   response_length = len(api_response)
                   print(f"✅ Got response: {response_length} chars")
                   
                   # Enhanced completion checking
                   if self._is_response_complete(api_response):
                       print(f"✅ Response appears complete")
                       return api_response
                   else:
                       print(f"❌ Response incomplete ({response_length} chars), retrying...")
                       continue
               else:
                   print(f"❌ No response from API (attempt {attempt + 1})")
                   continue
           
           print("⚠️ All API attempts failed, using enhanced fallback")
           # Enhanced fallback with intent consideration
           return self._generate_persona_fallback_enhanced(message, persona, pronunciation_analysis, grammar_analysis, intent_analysis)
           
       except Exception as e:
           print(f"Enhanced persona response error: {e}")
           traceback.print_exc()
           return self._generate_persona_fallback_enhanced(message, persona, pronunciation_analysis, grammar_analysis, intent_analysis)

    def _update_comprehensive_progress(self, username, user_message, bot_response, pronunciation_analysis, grammar_analysis, fluency_analysis, composite_score):
       """Update user progress with enhanced data tracking"""
       try:
           user_file = f"users/{username}.json"
           with open(user_file, 'r') as f:
               user_data = json.load(f)
           
           # Update scores with smoothing for stability
           old_scores = {
               'pronunciation': user_data['profile'].get('pronunciation_score', 0),
               'grammar': user_data['profile'].get('grammar_score', 0),
               'fluency': user_data['profile'].get('fluency_score', 0),
               'overall': user_data['profile'].get('proficiency_score', 0)
           }
           
           # Apply smoothing (80% old, 20% new) to prevent dramatic swings
           smoothing_factor = 0.2
           user_data['profile']['pronunciation_score'] = round(
               old_scores['pronunciation'] * (1 - smoothing_factor) + 
               pronunciation_analysis.get('score', 0) * smoothing_factor
           )
           user_data['profile']['grammar_score'] = round(
               old_scores['grammar'] * (1 - smoothing_factor) + 
               grammar_analysis.get('score', 0) * smoothing_factor
           )
           user_data['profile']['fluency_score'] = round(
               old_scores['fluency'] * (1 - smoothing_factor) + 
               fluency_analysis.get('score', 0) * smoothing_factor
           )
           user_data['profile']['proficiency_score'] = round(
               old_scores['overall'] * (1 - smoothing_factor) + 
               composite_score * smoothing_factor
           )
           
           # Update running averages and stats
           stats = user_data['stats']
           total_sessions = stats['total_sessions'] + 1
           
           stats['average_pronunciation_score'] = self._update_running_average(
               stats.get('average_pronunciation_score', 0), 
               pronunciation_analysis.get('score', 0), 
               total_sessions
           )
           stats['average_grammar_score'] = self._update_running_average(
               stats.get('average_grammar_score', 0), 
               grammar_analysis.get('score', 0), 
               total_sessions
           )
           stats['average_fluency_score'] = self._update_running_average(
               stats.get('average_fluency_score', 0), 
               fluency_analysis.get('score', 0), 
               total_sessions
           )
           stats['average_wpm'] = self._update_running_average(
               stats.get('average_wpm', 0), 
               fluency_analysis.get('words_per_minute', 0), 
               total_sessions
           )
           
           stats['total_sessions'] = total_sessions
           stats['last_practice'] = datetime.datetime.now().isoformat()
           
           # Enhanced conversation history
           if 'conversation_history' not in user_data:
               user_data['conversation_history'] = []
           
           user_data['conversation_history'].append({
               'timestamp': datetime.datetime.now().isoformat(),
               'user_message': user_message,
               'bot_response': bot_response,
               'scores': {
                   'pronunciation': pronunciation_analysis.get('score', 0),
                   'grammar': grammar_analysis.get('score', 0),
                   'fluency': fluency_analysis.get('score', 0),
                   'composite': composite_score
               },
               'analysis_details': {
                   'pronunciation_errors': len(pronunciation_analysis.get('mispronunciations', [])),
                   'grammar_errors': len(grammar_analysis.get('errors', [])),
                   'filler_count': fluency_analysis.get('filler_count', 0),
                   'wpm': fluency_analysis.get('words_per_minute', 0)
               }
           })
           
           # Keep only last 50 conversations for performance
           user_data['conversation_history'] = user_data['conversation_history'][-50:]
           
           # Save updated data
           with open(user_file, 'w') as f:
               json.dump(user_data, f, indent=2)
           
           print(f"✅ Enhanced progress updated for {username}")
           
       except Exception as e:
           print(f"Enhanced progress update error: {e}")
           traceback.print_exc()

    def _update_running_average(self, current_avg, new_value, count):
       """Update running average with new value"""
       if count == 1:
           return new_value
       return round(((current_avg * (count - 1)) + new_value) / count, 1)

    def _register_routes(self):
       # Enhanced authentication routes
       @self.app.route('/api/auth/signup', methods=['POST'])
       def signup():
           try:
               data = request.get_json()
               username = data.get('username', '').strip()
               email = data.get('email', '').strip()
               password = data.get('password', '')
               full_name = data.get('fullName', '').strip()
               initial_level = data.get('initialLevel', 'auto')  # New: manual level selection
               
               if not all([username, email, password, full_name]):
                   return jsonify({'error': 'All fields are required'}), 400
               
               if len(password) < 6:
                   return jsonify({'error': 'Password must be at least 6 characters'}), 400
               
               user_file = f"users/{username}.json"
               if os.path.exists(user_file):
                   return jsonify({'error': 'Username already exists'}), 409
               
               # Determine initial proficiency score based on level selection
               if initial_level == 'auto':
                   proficiency_score = 25
                   level = 'beginner'
               elif initial_level == 'beginner':
                   proficiency_score = 35
                   level = 'beginner'
               elif initial_level == 'intermediate':
                   proficiency_score = 60
                   level = 'intermediate'
               elif initial_level == 'advanced':
                   proficiency_score = 80
                   level = 'advanced'
               else:
                   proficiency_score = 25
                   level = 'beginner'
               
               # Enhanced user profile
               user_data = {
                   'id': str(uuid.uuid4()),
                   'username': username,
                   'email': email,
                   'full_name': full_name,
                   'password_hash': generate_password_hash(password),
                   'created_at': datetime.datetime.now().isoformat(),
                   'profile': {
                       'level': level,
                       'current_persona': level,
                       'proficiency_score': proficiency_score,
                       'pronunciation_score': proficiency_score,
                       'grammar_score': proficiency_score,
                       'fluency_score': proficiency_score,
                       'manual_level_override': initial_level != 'auto',
                       'goals': {
                           'daily_practice_time': 15,
                           'weekly_vocab_target': 20,
                           'current_focus': 'conversation'
                       },
                       'preferences': {
                           'voice_enabled': True,
                           'difficulty': 'adaptive',
                           'topics': ['general', 'conversation'],
                           'correction_style': 'gentle',
                           'pronunciation_feedback': True,
                           'auto_level_adjustment': initial_level == 'auto'
                       }
                   },
                   'stats': {
                       'total_sessions': 0,
                       'total_practice_time': 0,
                       'words_learned': 0,
                       'grammar_improvements': 0,
                       'pronunciation_improvements': 0,
                       'streak_days': 0,
                       'last_practice': None,
                       'average_wpm': 0,
                       'average_pronunciation_score': proficiency_score,
                       'average_grammar_score': proficiency_score,
                       'average_fluency_score': proficiency_score
                   },
                   'conversation_history': [],
                   'pronunciation_history': [],
                   'grammar_history': [],
                   'fluency_history': [],
                   'vocabulary': {
                       'learning': [],
                       'mastered': [],
                       'review_needed': [],
                       'mispronounced': [],
                       'total_encountered': 0
                   },
                   'session_history': [],
                   'level_change_history': [
                       {
                           'timestamp': datetime.datetime.now().isoformat(),
                           'from_level': None,
                           'to_level': level,
                           'score': proficiency_score,
                           'method': 'manual' if initial_level != 'auto' else 'auto'
                       }
                   ]
               }
               
               with open(user_file, 'w') as f:
                   json.dump(user_data, f, indent=2)
               
               access_token = create_access_token(identity=username)
               
               return jsonify({
                   'message': 'Account created successfully!',
                   'token': access_token,
                   'user': {
                       'username': username,
                       'full_name': full_name,
                       'email': email,
                       'level': level,
                       'proficiency_score': proficiency_score
                   }
               }), 201
               
           except Exception as e:
               print(f"Signup error: {e}")
               traceback.print_exc()
               return jsonify({'error': 'Server error during signup'}), 500

       @self.app.route('/api/auth/login', methods=['POST'])
       def login():
           try:
               data = request.get_json()
               username = data.get('username', '').strip()
               password = data.get('password', '')
               
               if not username or not password:
                   return jsonify({'error': 'Username and password required'}), 400
               
               user_file = f"users/{username}.json"
               if not os.path.exists(user_file):
                   return jsonify({'error': 'Invalid username or password'}), 401
               
               with open(user_file, 'r') as f:
                   user_data = json.load(f)
               
               if not check_password_hash(user_data['password_hash'], password):
                   return jsonify({'error': 'Invalid username or password'}), 401
               
               access_token = create_access_token(identity=username)
               
               return jsonify({
                   'message': 'Login successful!',
                   'token': access_token,
                   'user': {
                       'username': username,
                       'full_name': user_data['full_name'],
                       'email': user_data['email'],
                       'level': user_data['profile']['level'],
                       'proficiency_score': user_data['profile'].get('proficiency_score', 25)
                   }
               }), 200
               
           except Exception as e:
               print(f"Login error: {e}")
               return jsonify({'error': 'Server error during login'}), 500

       # Enhanced chat endpoint with fixed response cut-off and intent detection
       @self.app.route('/api/chat/message', methods=['POST'])
       @jwt_required()
       def chat_message():
           try:
               username = get_jwt_identity()
               data = request.get_json()
               message = data.get('message', '').strip()
               conversation_mode = data.get('conversation_mode', 'natural')
               
               if not message:
                   return jsonify({'error': 'Message cannot be empty'}), 400
               
               # Load user data
               user_file = f"users/{username}.json"
               with open(user_file, 'r') as f:
                   user_data = json.load(f)
               
               print(f"📝 Processing message from {username}: {message[:50]}...")
               
               # Comprehensive analysis
               start_time = time.time()
               
               # NEW: Detect sentence intent type
               intent_analysis = self._detect_sentence_intent(message)
               
               # 1. Enhanced pronunciation analysis
               pronunciation_analysis = self._analyze_pronunciation_enhanced(message, user_data)
               
               # 2. Enhanced grammar analysis  
               grammar_analysis = self._analyze_grammar_enhanced(message)
               
               # 3. Enhanced fluency analysis
               fluency_analysis = self._analyze_fluency_enhanced(message, user_data)
               
               # 4. Calculate composite proficiency score
               composite_score = self._calculate_composite_score(
                   pronunciation_analysis, grammar_analysis, fluency_analysis
               )
               
               # 5. Update user level only if auto-adjustment is enabled
               old_level = user_data['profile']['level']
               new_level = old_level
               persona_changed = False
               
               if user_data['profile']['preferences'].get('auto_level_adjustment', True):
                   new_level = self._determine_level(composite_score)
                   if new_level != old_level:
                       user_data['profile']['level'] = new_level
                       user_data['profile']['current_persona'] = new_level
                       persona_changed = True
                       
                       # Record automatic level change
                       if 'level_change_history' not in user_data:
                           user_data['level_change_history'] = []
                       
                       user_data['level_change_history'].append({
                           'timestamp': datetime.datetime.now().isoformat(),
                           'from_level': old_level,
                           'to_level': new_level,
                           'score': composite_score,
                           'method': 'auto'
                       })
                       
                       print(f"🎭 User {username} level changed: {old_level} → {new_level}")
               
               # 6. Generate response using appropriate persona with enhanced API handling and intent
               current_persona = user_data['profile']['current_persona']
               bot_response = self._generate_persona_response_enhanced(
                   message, current_persona, user_data, pronunciation_analysis, 
                   grammar_analysis, fluency_analysis, intent_analysis
               )
               
               # 7. Generate enhanced accent correction feedback
               accent_feedback = None
               if (pronunciation_analysis['mispronunciations'] or 
                   pronunciation_analysis['score'] < 70):
                   accent_feedback = self._generate_accent_correction_enhanced(
                       message, pronunciation_analysis
                   )
               
               # 8. Update user progress
               self._update_comprehensive_progress(
                   username, message, bot_response, pronunciation_analysis,
                   grammar_analysis, fluency_analysis, composite_score
               )
               
               processing_time = time.time() - start_time
               print(f"⚡ Analysis completed in {processing_time:.2f}s")
               
               response_data = {
                   'response': bot_response,
                   'analysis': {
                       'intent': intent_analysis,  # NEW: Include intent in response
                       'pronunciation': {
                           'score': pronunciation_analysis['score'],
                           'mispronunciations': pronunciation_analysis['mispronunciations'][:3],
                           'accuracy': pronunciation_analysis['accuracy'],
                           'phoneme_errors': pronunciation_analysis.get('phoneme_errors', [])
                       },
                       'grammar': {
                           'score': grammar_analysis['score'],
                           'errors': len(grammar_analysis['errors']),
                           'suggestions': grammar_analysis['errors'][:2],
                           'error_types': grammar_analysis.get('error_types', [])
                       },
                       'fluency': {
                           'score': fluency_analysis['score'],
                           'wpm': fluency_analysis['words_per_minute'],
                           'filler_count': fluency_analysis['filler_count'],
                           'pause_analysis': fluency_analysis.get('pause_analysis', {})
                       },
                       'composite_score': composite_score,
                       'level': new_level,
                       'persona_changed': persona_changed
                   },
                   'accent_feedback': accent_feedback,
                   'processing_time': round(processing_time, 2)
               }
               
               # Add detailed feedback in full_feedback mode
               if conversation_mode == 'full_feedback':
                   response_data['detailed_feedback'] = self._prepare_detailed_feedback(
                       pronunciation_analysis, grammar_analysis, fluency_analysis
                   )
               
               return jsonify(response_data), 200
               
           except Exception as e:
               print(f"Chat error: {e}")
               traceback.print_exc()
               return jsonify({'error': 'Could not process message'}), 500

       @self.app.route('/api/user/stats', methods=['GET'])
       @jwt_required()
       def get_stats():
           try:
               username = get_jwt_identity()
               user_file = f"users/{username}.json"
               
               if not os.path.exists(user_file):
                   return jsonify({'error': 'User not found'}), 404
               
               with open(user_file, 'r') as f:
                   user_data = json.load(f)
               
               # Calculate recent sessions (this week)
               recent_sessions = user_data.get('session_history', [])
               current_time = datetime.datetime.now()
               week_ago = current_time - datetime.timedelta(days=7)
               
               sessions_this_week = 0
               for session in recent_sessions:
                   try:
                       session_time = datetime.datetime.fromisoformat(session.get('timestamp', ''))
                       if session_time >= week_ago:
                           sessions_this_week += 1
                   except:
                       continue
               
               # Enhanced statistics
               stats = {
                   'basic': {
                       'total_sessions': user_data.get('stats', {}).get('total_sessions', 0),
                       'total_practice_time': user_data.get('stats', {}).get('total_practice_time', 0),
                       'words_learned': user_data.get('stats', {}).get('words_learned', 0),
                       'grammar_improvements': user_data.get('stats', {}).get('grammar_improvements', 0),
                       'pronunciation_improvements': user_data.get('stats', {}).get('pronunciation_improvements', 0),
                       'streak_days': user_data.get('stats', {}).get('streak_days', 0),
                       'average_wpm': user_data.get('stats', {}).get('average_wpm', 0),
                       'average_pronunciation_score': user_data.get('stats', {}).get('average_pronunciation_score', 0),
                       'average_grammar_score': user_data.get('stats', {}).get('average_grammar_score', 0),
                       'average_fluency_score': user_data.get('stats', {}).get('average_fluency_score', 0)
                   },
                   'proficiency': {
                       'overall_score': user_data.get('profile', {}).get('proficiency_score', 25),
                       'pronunciation_score': user_data.get('profile', {}).get('pronunciation_score', 0),
                       'grammar_score': user_data.get('profile', {}).get('grammar_score', 0),
                       'fluency_score': user_data.get('profile', {}).get('fluency_score', 0),
                       'current_level': user_data.get('profile', {}).get('level', 'beginner'),
                       'current_persona': user_data.get('profile', {}).get('current_persona', 'beginner')
                   },
                   'vocabulary': {
                       'total_learning': len(user_data.get('vocabulary', {}).get('learning', [])),
                       'total_mastered': len(user_data.get('vocabulary', {}).get('mastered', [])),
                       'mispronounced': len(user_data.get('vocabulary', {}).get('mispronounced', [])),
                       'review_needed': len(user_data.get('vocabulary', {}).get('review_needed', [])),
                       'total_words': user_data.get('vocabulary', {}).get('total_encountered', 0)
                   },
                   'recent_activity': {
                       'sessions_this_week': sessions_this_week,
                       'avg_pronunciation_score': user_data.get('stats', {}).get('average_pronunciation_score', 0),
                       'avg_grammar_score': user_data.get('stats', {}).get('average_grammar_score', 0),
                       'avg_fluency_score': user_data.get('stats', {}).get('average_fluency_score', 0),
                       'total_errors_corrected': len(user_data.get('grammar_history', []))
                   }
               }
               
               return jsonify(stats), 200
               
           except Exception as e:
               print(f"Stats error: {e}")
               traceback.print_exc()
               return jsonify({'error': 'Could not load stats'}), 500

       @self.app.route('/api/user/profile', methods=['GET'])
       @jwt_required()
       def get_profile():
           try:
               username = get_jwt_identity()
               user_file = f"users/{username}.json"
               
               with open(user_file, 'r') as f:
                   user_data = json.load(f)
               
               profile_data = {
                   'username': user_data['username'],
                   'full_name': user_data['full_name'],
                   'email': user_data['email'],
                   'profile': user_data['profile'],
                   'stats': user_data['stats'],
                   'created_at': user_data['created_at'],
                   'recent_scores': {
                       'pronunciation': user_data.get('pronunciation_history', [])[-10:],
                       'grammar': user_data.get('grammar_history', [])[-10:],
                       'fluency': user_data.get('fluency_history', [])[-10:]
                   },
                   'level_change_history': user_data.get('level_change_history', [])[-5:]
               }
               
               return jsonify(profile_data), 200
               
           except Exception as e:
               print(f"Profile error: {e}")
               return jsonify({'error': 'Could not load profile'}), 500

       # Add manual level selection endpoint
       @self.app.route('/api/user/set-level', methods=['POST'])
       @jwt_required()
       def set_manual_level():
           try:
               username = get_jwt_identity()
               data = request.get_json()
               new_level = data.get('level', '').lower()
               
               if new_level not in ['beginner', 'intermediate', 'advanced', 'native']:
                   return jsonify({'error': 'Invalid level'}), 400
               
               user_file = f"users/{username}.json"
               with open(user_file, 'r') as f:
                   user_data = json.load(f)
               
               old_level = user_data['profile']['level']
               
               # Set new level and corresponding score
               level_scores = {
                   'beginner': 35,
                   'intermediate': 60,
                   'advanced': 80,
                   'native': 95
               }
               
               user_data['profile']['level'] = new_level
               user_data['profile']['current_persona'] = new_level
               user_data['profile']['manual_level_override'] = True
               user_data['profile']['preferences']['auto_level_adjustment'] = False
               
               # Update scores to match level
               new_score = level_scores[new_level]
               user_data['profile']['proficiency_score'] = new_score
               user_data['profile']['pronunciation_score'] = new_score
               user_data['profile']['grammar_score'] = new_score
               user_data['profile']['fluency_score'] = new_score
               
               # Record level change
               if 'level_change_history' not in user_data:
                   user_data['level_change_history'] = []
               
               user_data['level_change_history'].append({
                   'timestamp': datetime.datetime.now().isoformat(),
                   'from_level': old_level,
                   'to_level': new_level,
                   'score': new_score,
                   'method': 'manual'
               })
               
               with open(user_file, 'w') as f:
                   json.dump(user_data, f, indent=2)
               
               print(f"🎭 User {username} manually changed level: {old_level} → {new_level}")
               
               return jsonify({
                   'message': f'Level changed to {new_level}',
                   'level': new_level,
                   'proficiency_score': new_score,
                   'level_changed': True
               }), 200
               
           except Exception as e:
               print(f"Set level error: {e}")
               return jsonify({'error': 'Failed to update level'}), 500

       # Health check
       @self.app.route('/api/health', methods=['GET'])
       def health_check():
           return jsonify({
               'status': 'healthy',
               'version': '3.1',
               'features': [
                   'enhanced_pronunciation_scoring', 
                   'improved_grammar_analysis', 
                   'advanced_fluency_metrics',
                   'manual_level_selection',
                   'fixed_response_cutoff',
                   'enhanced_accent_correction',
                   'intent_detection',
                   'session_summaries'
               ],
               'nlp_tools': {
                   'spacy_loaded': bool(nlp),
                   'grammar_tool_loaded': bool(grammar_tool),
                   'pronouncing_available': True
               },
               'timestamp': datetime.datetime.now().isoformat()
           }), 200

       @self.app.route('/')
       def home():
           return jsonify({
               'message': 'Enhanced AI English Tutor API v3.1',
               'description': 'Advanced pronunciation, grammar, and fluency analysis with manual level selection',
               'fixed_issues': [
                   'Enhanced phoneme-level pronunciation scoring',
                   'Fixed chatbot response cut-off bug',
                   'Added manual level selection option',
                   'Improved accent correction with drill exercises',
                   'Enhanced grammar and fluency metrics',
                   'Professional UI styling improvements',
                   'Intent detection and adaptive responses',
                   'Session summaries and advanced analytics'
               ],
               'creator': 'Enhanced for FYP by Claude v3.1',
               'endpoints': {
                   'auth': '/api/auth/login|signup',
                   'chat': '/api/chat/message',
                   'level': '/api/user/set-level',
                   'pronunciation': '/api/pronunciation/assess',
                   'profile': '/api/user/profile',
                   'health': '/api/health'
               }
           })

    def _generate_accent_correction_enhanced(self, message, pronunciation_analysis):
       """Enhanced accent correction with drill-based exercises"""
       try:
           if not pronunciation_analysis.get('mispronunciations'):
               return None
           
           mispronunciations = pronunciation_analysis['mispronunciations'][:3]
           
           # Build structured drill-based correction
           correction_parts = []
           
           # 1. Acknowledgment
           correction_parts.append(f"I heard you say: '{message}'")
           
           # 2. Specific phonetic guidance
           for mp in mispronunciations[:2]:  # Focus on top 2 errors
               word = mp['word']
               tips = mp.get('common_errors', [])
               
               if tips:
                   correction_parts.append(f"For '{word}': {tips[0]}")
           
           # 3. Drill exercises
           drill_words = []
           practice_sounds = set()
           
           for mp in mispronunciations:
               word = mp['word']
               phoneme_errors = mp.get('phoneme_errors', [])
               practice_sounds.update(phoneme_errors)
               drill_words.append(word)
           
           # Generate practice exercises
           if practice_sounds:
               sound_exercises = self._generate_drill_exercises(practice_sounds, drill_words)
               correction_parts.append("Practice these:")
               correction_parts.extend(sound_exercises)
           
           # 4. Encouragement
           score = pronunciation_analysis.get('score', 70)
           if score >= 60:
               correction_parts.append("You're doing well! Keep practicing these sounds.")
           else:
               correction_parts.append("Don't worry, pronunciation takes practice. Try these exercises.")
           
           textual_feedback = " ".join(correction_parts)
           
           # Enhanced metadata
           correction_metadata = {
               'mispronounced_words': [
                   {
                       'word': mp['word'],
                       'expected_phonemes': mp.get('expected_phonemes', []),
                       'accuracy': mp.get('accuracy', 0),
                       'tips': mp.get('common_errors', []),
                       'phoneme_errors': mp.get('phoneme_errors', [])
                   }
                   for mp in mispronunciations
               ],
               'overall_score': pronunciation_analysis.get('score', 0),
               'focus_sounds': list(practice_sounds),
               'practice_words': drill_words,
               'drill_exercises': sound_exercises if practice_sounds else []
           }
           
           return {
               'textual_feedback': textual_feedback,
               'metadata': correction_metadata,
               'drill_based': True,
               'timestamp': datetime.datetime.now().isoformat()
           }
           
       except Exception as e:
           print(f"Enhanced accent correction error: {e}")
           return {
               'textual_feedback': "Keep practicing your pronunciation! Focus on speaking clearly and slowly.",
               'metadata': {'error': str(e)},
               'timestamp': datetime.datetime.now().isoformat()
           }

    def _generate_drill_exercises(self, practice_sounds, drill_words):
       """Generate specific drill exercises for problematic sounds"""
       exercises = []
       
       sound_drills = {
           'TH': [
               "Repeat: think - thank - three - through",
               "Practice: 'Put your tongue between your teeth'",
               "Try: this, that, the, thing"
           ],
           'R': [
               "Repeat: red - right - really - crystal",
               "Practice: 'Curl your tongue back slightly'",
               "Try: around, pretty, friend, great"
           ],
           'L': [
               "Repeat: light - love - little - local",
               "Practice: 'Touch tongue to roof of mouth'", 
               "Try: help, people, family, well"
           ],
           'V': [
               "Repeat: very - voice - video - visit",
               "Practice: 'Bottom lip touches upper teeth'",
               "Try: have, give, love, live"
           ],
           'W': [
               "Repeat: water - wonderful - we - why",
               "Practice: 'Round your lips like whistling'",
               "Try: one, when, where, what"
           ]
       }
       
       for sound in practice_sounds:
           if sound in sound_drills:
               exercises.extend(sound_drills[sound][:2])  # Take first 2 exercises per sound
       
       # Add word-specific exercises
       if drill_words:
           exercises.append(f"Repeat slowly: {' - '.join(drill_words[:3])}")
       
       return exercises[:4]  # Limit to 4 exercises max

    def run(self, debug=True, port=5000):
       """Run the enhanced Flask app"""
       print("🚀 Enhanced AI English Tutor Backend v3.1 Starting!")
       print(f"🌐 Server: http://127.0.0.1:{port}")
       print("✨ Enhanced Features:")
       print("   📊 Advanced phoneme-level pronunciation scoring")
       print("   📝 Enhanced grammar analysis with error categorization")
       print("   🎯 Improved fluency metrics with pause analysis")
       print("   🎭 Manual level selection with auto-adjustment toggle")
       print("   🔧 Fixed chatbot response cut-off bug")
       print("   💬 Enhanced accent correction with drill exercises")
       print("   🧠 Intent detection and adaptive responses")
       print("   📋 Session summaries and advanced analytics")
       print("💡 Tip: Set GROQ_API_KEY environment variable for AI responses")
       
       self.app.run(debug=debug, port=port)

# Create app instance
app_instance = EnhancedAIEnglishTutor()

# For production deployment
app = app_instance.app

if __name__ == "__main__":
   app_instance.run()