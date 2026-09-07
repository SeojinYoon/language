/**
 * =========================================================
 * VOCABMASTER APPLICATION LOGIC
 * Core Image & Nuance Lab
 * =========================================================
 */

(function () {
  'use strict';

  // State Management
  const state = {
    allData: window.VOCAB_DATA || [],
    filteredData: [],
    currentIndex: 0,
    currentWord: null,
    
    // Filters & Mode
    currentView: 'quiz-view', // quiz-view | flashcard-view | dict-view | stats-view
    sourceFilter: 'all', // all | Dissimilarities | Words Organized
    categoryFilter: 'all',
    reviewOnly: false,
    quizType: 'typing', // typing | choice
    
    // Hint state
    revealedLetters: 0,
    isAnswered: false,
    
    // Audio & Theme
    soundEnabled: true,
    theme: localStorage.getItem('vm_theme') || 'dark',

    // Persistence Stats
    stats: JSON.parse(localStorage.getItem('vm_stats')) || {
      streak: 0,
      bestStreak: 0,
      xp: 0,
      totalAnswered: 0,
      correctCount: 0,
      wrongIds: [],
      bookmarks: [],
      mastery: {} // id -> 1 (hard), 2 (good), 3 (easy)
    }
  };

  // Web Audio Synthesizer (Zero-dependency sound effects)
  const soundSynth = {
    ctx: null,
    init() {
      if (!this.ctx) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) this.ctx = new AudioContext();
      }
    },
    playCorrect() {
      if (!state.soundEnabled) return;
      this.init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;
      
      const osc1 = this.ctx.createOscillator();
      const osc2 = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc1.type = 'sine';
      osc2.type = 'triangle';
      osc1.frequency.setValueAtTime(523.25, now); // C5
      osc1.frequency.exponentialRampToValueAtTime(659.25, now + 0.1); // E5
      osc1.frequency.exponentialRampToValueAtTime(783.99, now + 0.2); // G5
      osc2.frequency.setValueAtTime(1046.50, now + 0.2); // C6

      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.45);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(this.ctx.destination);

      osc1.start(now);
      osc2.start(now + 0.2);
      osc1.stop(now + 0.45);
      osc2.stop(now + 0.45);
    },
    playWrong() {
      if (!state.soundEnabled) return;
      this.init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(180, now);
      osc.frequency.linearRampToValueAtTime(110, now + 0.25);

      gain.gain.setValueAtTime(0.25, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.3);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start(now);
      osc.stop(now + 0.3);
    },
    playFlip() {
      if (!state.soundEnabled) return;
      this.init();
      if (!this.ctx) return;
      const now = this.ctx.currentTime;

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = 'sine';
      osc.frequency.setValueAtTime(300, now);
      osc.frequency.exponentialRampToValueAtTime(600, now + 0.08);

      gain.gain.setValueAtTime(0.1, now);
      gain.gain.exponentialRampToValueAtTime(0.01, now + 0.1);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start(now);
      osc.stop(now + 0.1);
    }
  };

  // Web Speech TTS
  function speakWord(text) {
    if (!('speechSynthesis' in window)) {
      showToast('브라우저가 음성 합성을 지원하지 않습니다.', 'info');
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 0.95;
    
    // Pick good natural English voice if available
    const voices = window.speechSynthesis.getVoices();
    const enVoice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha') || v.name.includes('Daniel')));
    if (enVoice) utterance.voice = enVoice;

    window.speechSynthesis.speak(utterance);
  }

  // Toast Notification
  function showToast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${msg}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 2500);
  }

  // Save Stats to LocalStorage
  function saveStats() {
    localStorage.setItem('vm_stats', JSON.stringify(state.stats));
    updateHeaderStats();
  }

  function updateHeaderStats() {
    document.getElementById('header-streak-count').textContent = state.stats.streak;
    document.getElementById('header-xp-count').textContent = `${state.stats.xp} XP`;
  }

  // Utility: Shuffle Array (Fisher-Yates)
  function shuffleArray(arr) {
    const copy = [...arr];
    for (let i = copy.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy;
  }

  // Utility: Category-Grouped Shuffle
  // 카테고리 순서를 랜덤하게 섞고, 각 카테고리 내부의 단어들도 랜덤하게 섞어서
  // 한 카테고리의 단어들이 모두 연속으로(1번씩) 출제되도록 구성
  function groupAndShuffleByCategory(list) {
    if (!list || list.length === 0) return [];

    const categoryMap = new Map();
    list.forEach(item => {
      const cat = item.category || '기타';
      if (!categoryMap.has(cat)) {
        categoryMap.set(cat, []);
      }
      categoryMap.get(cat).push(item);
    });

    const shuffledCategories = shuffleArray([...categoryMap.keys()]);
    let result = [];

    shuffledCategories.forEach(cat => {
      const wordsInCat = categoryMap.get(cat);
      const shuffledWords = shuffleArray(wordsInCat);
      result.push(...shuffledWords);
    });

    return result;
  }

  // Filter Data
  function applyFilters() {
    let list = [...state.allData];

    // Source Filter
    if (state.sourceFilter !== 'all') {
      list = list.filter(item => item.source === state.sourceFilter);
    }

    // Category Filter
    if (state.categoryFilter !== 'all') {
      list = list.filter(item => item.category === state.categoryFilter);
    }

    // Review Only Filter
    if (state.reviewOnly) {
      list = list.filter(item => 
        state.stats.wrongIds.includes(item.id) || 
        state.stats.bookmarks.includes(item.id) || 
        (state.stats.mastery[item.id] && state.stats.mastery[item.id] < 3)
      );
    }

    // 카테고리 단위로 묶여서 연이어 출제되도록 그룹 셔플 적용
    state.filteredData = groupAndShuffleByCategory(list);
    state.currentIndex = 0;
    
    // Populate Category dropdown based on source
    populateCategories();

    if (state.filteredData.length === 0) {
      showToast('조건에 맞는 단어가 없습니다. 필터를 조정해 주세요.', 'info');
    }

    renderCurrentView();
  }

  function populateCategories() {
    const select = document.getElementById('category-select');
    const currentVal = state.categoryFilter;
    select.innerHTML = '<option value="all">모든 카테고리 전체</option>';

    let pool = state.allData;
    if (state.sourceFilter !== 'all') {
      pool = pool.filter(item => item.source === state.sourceFilter);
    }

    const categories = [...new Set(pool.map(item => item.category))].sort();
    categories.forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat;
      opt.textContent = cat;
      if (cat === currentVal) opt.selected = true;
      select.appendChild(opt);
    });
  }

  // Shuffle filtered array
  function shuffleFilteredData() {
    state.filteredData = groupAndShuffleByCategory(state.filteredData);
    state.currentIndex = 0;
    showToast('카테고리 및 단어 순서가 무작위로 섞였습니다! 🔀', 'info');
    renderCurrentView();
  }

  // Cloze Generator (mask target word in sentence)
  function generateClozeSentence(example, targetWord) {
    if (!example || !targetWord) return '예문이 없습니다.';
    
    // Clean target word for regex
    const cleanWord = targetWord.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').trim();
    // Try to match whole word or root
    const regex = new RegExp(`\\b${cleanWord}(?:s|ed|ing|d|es)?\\b`, 'gi');
    
    if (regex.test(example)) {
      return example.replace(regex, '<span class="cloze-blank">_______</span>');
    }
    
    // Fallback: replace any occurrence
    return example.replace(new RegExp(cleanWord, 'gi'), '<span class="cloze-blank">_______</span>');
  }

  // Highlight target word in sentence
  function highlightWordInSentence(example, targetWord) {
    if (!example || !targetWord) return example || '';
    const cleanWord = targetWord.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').trim();
    const regex = new RegExp(`\\b(${cleanWord}(?:s|ed|ing|d|es)?)\\b`, 'gi');
    if (regex.test(example)) {
      return example.replace(regex, '<strong class="highlight-word">$1</strong>');
    }
    return example.replace(new RegExp(`(${cleanWord})`, 'gi'), '<strong class="highlight-word">$1</strong>');
  }

  // Hint Generator (글자수 밑줄 없이 힌트 요청 시 앞글자만 표시)
  function getHintSlots(word, revealedCount) {
    if (!word || revealedCount <= 0) return '';
    const letters = word.split('');
    let result = '';

    letters.forEach((char, idx) => {
      if (idx < revealedCount) {
        result += char.toUpperCase() + ' ';
      }
    });

    const trimmed = result.trim();
    return trimmed ? `힌트: ${trimmed}` : '';
  }

  // ================= QUIZ VIEW LOGIC =================
  function loadQuizQuestion() {
    if (state.filteredData.length === 0) {
      document.getElementById('quiz-meaning').textContent = '학습할 단어가 없습니다.';
      document.getElementById('quiz-core-image').textContent = '상단 필터에서 카테고리나 출처를 다시 선택해 주세요.';
      document.getElementById('quiz-focus').textContent = '';
      document.getElementById('quiz-cloze-example').textContent = '';
      return;
    }

    state.isAnswered = false;
    state.revealedLetters = 0;
    state.currentWord = state.filteredData[state.currentIndex];
    const item = state.currentWord;

    // Header Badges
    document.getElementById('quiz-source-badge').textContent = item.source;
    document.getElementById('quiz-category-badge').textContent = item.category;
    document.getElementById('quiz-counter').textContent = `카드 ${state.currentIndex + 1} / ${state.filteredData.length}`;

    // Clues
    document.getElementById('quiz-meaning').textContent = item.meaning || item.category;
    document.getElementById('quiz-core-image').textContent = item.core_image || '(코어 이미지가 등록되어 있지 않습니다)';
    document.getElementById('quiz-focus').textContent = item.focus || '(초점 설명이 등록되어 있지 않습니다)';

    // Example Section: Hide before answer is confirmed (정답 확인 전에는 예문 미노출)
    const exampleSection = document.getElementById('quiz-example-section');
    exampleSection.classList.add('hidden');
    document.getElementById('quiz-cloze-example').innerHTML = '';

    // Hint Bar: 글자 수 표현(_) 제거
    document.getElementById('hint-letter-slots').innerHTML = '';

    // Reset Answer Areas
    document.getElementById('quiz-feedback-box').classList.add('hidden');
    document.getElementById('quiz-input').value = '';
    document.getElementById('quiz-input').disabled = false;
    
    // Update Bookmark Button state
    updateBookmarkButton();

    // Render mode specific answers
    if (state.quizType === 'typing') {
      document.getElementById('typing-answer-container').classList.remove('hidden');
      document.getElementById('choice-answer-container').classList.add('hidden');
      setTimeout(() => document.getElementById('quiz-input').focus(), 50);
    } else {
      document.getElementById('typing-answer-container').classList.add('hidden');
      document.getElementById('choice-answer-container').classList.remove('hidden');
      renderMultipleChoiceOptions();
    }
  }

  function updateBookmarkButton() {
    const btn = document.getElementById('quiz-bookmark-btn');
    if (state.currentWord && state.stats.bookmarks.includes(state.currentWord.id)) {
      btn.style.color = 'var(--accent-amber)';
      btn.innerHTML = '<i data-lucide="bookmark-check"></i>';
    } else {
      btn.style.color = 'var(--text-secondary)';
      btn.innerHTML = '<i data-lucide="bookmark"></i>';
    }
    lucide.createIcons();
  }

  function toggleBookmark() {
    if (!state.currentWord) return;
    const id = state.currentWord.id;
    const idx = state.stats.bookmarks.indexOf(id);
    if (idx > -1) {
      state.stats.bookmarks.splice(idx, 1);
      showToast('북마크에서 제거되었습니다.', 'info');
    } else {
      state.stats.bookmarks.push(id);
      showToast('단어가 즐겨찾기에 추가되었습니다! ⭐', 'success');
    }
    saveStats();
    updateBookmarkButton();
  }

  function renderMultipleChoiceOptions() {
    const container = document.getElementById('choice-buttons-grid');
    container.innerHTML = '';
    if (!state.currentWord) return;

    const correctWord = state.currentWord.word;
    
    // Select 3 distractors
    // Priority: distractors from same category or same source
    let pool = state.allData.filter(item => item.word.toLowerCase() !== correctWord.toLowerCase());
    const sameCatPool = pool.filter(item => item.category === state.currentWord.category);
    
    let distractors = [];
    if (sameCatPool.length >= 3) {
      distractors = shuffleArray(sameCatPool).slice(0, 3).map(i => i.word);
    } else {
      distractors = shuffleArray(pool).slice(0, 3).map(i => i.word);
    }

    const options = shuffleArray([correctWord, ...distractors]);

    options.forEach((opt, idx) => {
      const btn = document.createElement('button');
      btn.className = 'choice-btn';
      btn.innerHTML = `
        <span>${opt}</span>
        <span class="choice-number">${idx + 1}</span>
      `;
      btn.addEventListener('click', () => handleChoiceAnswer(opt, btn));
      container.appendChild(btn);
    });
  }

  function cleanString(str) {
    return str.toLowerCase().replace(/[^a-z0-9]/g, '').trim();
  }

  function handleTypingSubmit(e) {
    if (e) e.preventDefault();
    if (state.isAnswered) {
      nextQuizQuestion();
      return;
    }

    const inputVal = document.getElementById('quiz-input').value.trim();
    if (!inputVal) return;

    const isCorrect = cleanString(inputVal) === cleanString(state.currentWord.word);
    finalizeAnswer(isCorrect);
  }

  function handleChoiceAnswer(selectedWord, btnElement) {
    if (state.isAnswered) return;
    const isCorrect = cleanString(selectedWord) === cleanString(state.currentWord.word);
    
    // Highlight choices
    const allBtns = document.querySelectorAll('.choice-btn');
    allBtns.forEach(b => {
      b.disabled = true;
      if (cleanString(b.querySelector('span').textContent) === cleanString(state.currentWord.word)) {
        b.classList.add('correct');
      }
    });

    if (!isCorrect) {
      btnElement.classList.add('wrong');
    }

    finalizeAnswer(isCorrect);
  }

  function finalizeAnswer(isCorrect) {
    state.isAnswered = true;
    state.stats.totalAnswered += 1;

    const feedbackBox = document.getElementById('quiz-feedback-box');
    feedbackBox.classList.remove('hidden');

    if (isCorrect) {
      state.stats.streak += 1;
      if (state.stats.streak > state.stats.bestStreak) {
        state.stats.bestStreak = state.stats.streak;
      }
      state.stats.xp += 10 + Math.min(state.stats.streak * 2, 20);
      state.stats.correctCount += 1;
      
      // Remove from wrong history if present
      const wIdx = state.stats.wrongIds.indexOf(state.currentWord.id);
      if (wIdx > -1) state.stats.wrongIds.splice(wIdx, 1);
      state.stats.mastery[state.currentWord.id] = 3;

      // Sound & Confetti
      soundSynth.playCorrect();
      if (typeof confetti === 'function' && state.stats.streak % 3 === 0) {
        confetti({ particleCount: 60, spread: 70, origin: { y: 0.7 } });
      }

      feedbackBox.className = 'feedback-box correct';
      document.getElementById('feedback-message').textContent = '정답입니다! 완벽해요 🎉';
      document.getElementById('feedback-icon').setAttribute('data-lucide', 'check-circle');
    } else {
      state.stats.streak = 0;
      if (!state.stats.wrongIds.includes(state.currentWord.id)) {
        state.stats.wrongIds.push(state.currentWord.id);
      }
      state.stats.mastery[state.currentWord.id] = 1;

      soundSynth.playWrong();

      feedbackBox.className = 'feedback-box wrong';
      document.getElementById('feedback-message').textContent = '아쉽네요! 복습 목록에 추가되었습니다.';
      document.getElementById('feedback-icon').setAttribute('data-lucide', 'x-circle');
    }

    // Revealed Word Info
    document.getElementById('feedback-revealed-word').textContent = state.currentWord.word;
    document.getElementById('feedback-revealed-meaning').textContent = state.currentWord.meaning || state.currentWord.category;

    // Reveal Example Section after answer is confirmed (정답 확인 후 예문 노출)
    const exampleSection = document.getElementById('quiz-example-section');
    if (state.currentWord.examples && state.currentWord.examples.length > 0) {
      exampleSection.classList.remove('hidden');
      const highlighted = highlightWordInSentence(state.currentWord.examples[0], state.currentWord.word);
      document.getElementById('quiz-cloze-example').innerHTML = `"${highlighted}"`;
    } else {
      exampleSection.classList.add('hidden');
    }

    // List all full examples in feedback box
    const examplesList = document.getElementById('feedback-examples-list');
    examplesList.innerHTML = '';
    if (state.currentWord.examples && state.currentWord.examples.length > 0) {
      state.currentWord.examples.forEach(ex => {
        const line = document.createElement('div');
        line.className = 'example-line';
        const highlightedEx = highlightWordInSentence(ex, state.currentWord.word);
        line.innerHTML = `
          <span>${highlightedEx}</span>
          <button class="mini-tts-btn" title="예문 듣기"><i data-lucide="volume-2"></i></button>
        `;
        line.querySelector('button').addEventListener('click', () => speakWord(ex));
        examplesList.appendChild(line);
      });
    }

    lucide.createIcons();
    saveStats();

    // Auto speak the target word
    setTimeout(() => speakWord(state.currentWord.word), 200);
  }

  function revealLetterHint() {
    if (state.isAnswered || !state.currentWord) return;
    const len = state.currentWord.word.length;
    if (state.revealedLetters < len) {
      state.revealedLetters += 1;
      document.getElementById('hint-letter-slots').innerHTML = getHintSlots(state.currentWord.word, state.revealedLetters);
      showToast(`힌트: 앞글자 ${state.revealedLetters}개가 공개되었습니다. 💡`, 'info');
    }
  }

  function revealAnswerInstantly() {
    if (state.isAnswered || !state.currentWord) return;
    finalizeAnswer(false);
  }

  function nextQuizQuestion() {
    if (state.currentIndex < state.filteredData.length - 1) {
      state.currentIndex += 1;
    } else {
      state.currentIndex = 0;
      state.filteredData = groupAndShuffleByCategory(state.filteredData);
      showToast('모든 단어 카드를 한 바퀴 돌았습니다! 새로운 무작위 순서로 시작합니다. 🎯', 'success');
    }
    loadQuizQuestion();
  }

  // ================= FLASHCARD VIEW LOGIC =================
  function loadFlashcard() {
    if (state.filteredData.length === 0) return;
    const item = state.filteredData[state.currentIndex];
    if (!item) return;

    const scene = document.getElementById('flashcard-scene');
    scene.classList.remove('flipped');

    document.getElementById('fc-counter').textContent = `카드 ${state.currentIndex + 1} / ${state.filteredData.length}`;

    // Front
    document.getElementById('fc-front-category').textContent = item.category;
    document.getElementById('fc-front-source').textContent = item.source;
    document.getElementById('fc-front-meaning').textContent = item.meaning || item.category;
    document.getElementById('fc-front-core').textContent = item.core_image || '-';
    document.getElementById('fc-front-focus').textContent = item.focus || '-';

    // Back
    document.getElementById('fc-back-category').textContent = item.category;
    document.getElementById('fc-back-word').textContent = item.word;
    document.getElementById('fc-back-meaning').textContent = item.meaning || item.category;

    const fcExamples = document.getElementById('fc-back-examples');
    fcExamples.innerHTML = '';
    if (item.examples && item.examples.length > 0) {
      item.examples.forEach(ex => {
        const p = document.createElement('p');
        p.className = 'example-line';
        p.innerHTML = `<span>> ${ex}</span>`;
        fcExamples.appendChild(p);
      });
    }

    lucide.createIcons();
  }

  function flipFlashcard() {
    const scene = document.getElementById('flashcard-scene');
    soundSynth.playFlip();
    scene.classList.toggle('flipped');
    if (scene.classList.contains('flipped')) {
      const item = state.filteredData[state.currentIndex];
      if (item) speakWord(item.word);
    }
  }

  function rateFlashcard(rating) {
    const item = state.filteredData[state.currentIndex];
    if (!item) return;

    state.stats.totalAnswered += 1;
    state.stats.mastery[item.id] = rating;

    if (rating === 3) {
      state.stats.xp += 5;
      state.stats.streak += 1;
      const wIdx = state.stats.wrongIds.indexOf(item.id);
      if (wIdx > -1) state.stats.wrongIds.splice(wIdx, 1);
    } else if (rating === 1) {
      state.stats.streak = 0;
      if (!state.stats.wrongIds.includes(item.id)) state.stats.wrongIds.push(item.id);
    }

    saveStats();

    if (state.currentIndex < state.filteredData.length - 1) {
      state.currentIndex += 1;
    } else {
      state.currentIndex = 0;
      showToast('플래시카드 한 세트를 완료했습니다! 🌟', 'success');
    }
    loadFlashcard();
  }

  // ================= DICTIONARY VIEW LOGIC =================
  function renderDictionary(searchTerm = '') {
    const grid = document.getElementById('dict-cards-grid');
    grid.innerHTML = '';

    // 사전 뷰는 알파벳순으로 정렬하여 보기 쉽게 제공
    let items = [...state.filteredData].sort((a, b) => a.word.localeCompare(b.word));
    if (searchTerm.trim()) {
      const term = searchTerm.toLowerCase();
      items = items.filter(item => 
        item.word.toLowerCase().includes(term) ||
        (item.meaning && item.meaning.toLowerCase().includes(term)) ||
        (item.core_image && item.core_image.toLowerCase().includes(term)) ||
        (item.focus && item.focus.toLowerCase().includes(term)) ||
        (item.examples && item.examples.some(ex => ex.toLowerCase().includes(term)))
      );
    }

    document.getElementById('dict-search-result-count').textContent = `총 ${items.length.toLocaleString()}개 단어 표시 중`;

    // Render cards (virtualize / limit initial slice for speed)
    const displaySlice = items.slice(0, 150);

    displaySlice.forEach(item => {
      const card = document.createElement('div');
      card.className = 'dict-card';
      card.innerHTML = `
        <div class="dict-card-top">
          <span class="badge ${item.source === 'Dissimilarities' ? 'source-badge' : 'category-badge'}">${item.category}</span>
          <button class="mini-tts-btn" title="발음 듣기"><i data-lucide="volume-2"></i></button>
        </div>
        <h3 class="dict-card-word">${item.word}</h3>
        <p class="dict-card-meaning">${item.meaning || item.category}</p>
        ${item.core_image ? `<p class="dict-card-core"><strong>코어 이미지:</strong> ${item.core_image}</p>` : ''}
        ${item.focus ? `<p class="dict-card-focus"><strong>초점:</strong> ${item.focus}</p>` : ''}
      `;
      card.querySelector('.mini-tts-btn').addEventListener('click', (e) => {
        e.stopPropagation();
        speakWord(item.word);
      });
      grid.appendChild(card);
    });

    if (items.length > 150) {
      const note = document.createElement('div');
      note.style.gridColumn = '1 / -1';
      note.style.textAlign = 'center';
      note.style.padding = '1.5rem';
      note.style.color = 'var(--text-muted)';
      note.textContent = `(원활한 성능을 위해 검색어에 매칭된 상위 150개를 표시하고 있습니다. 세부 검색어로 더 좁혀보세요)`;
      grid.appendChild(note);
    }

    lucide.createIcons();
  }

  // ================= STATS VIEW LOGIC =================
  function renderStats() {
    document.getElementById('stats-total-answered').textContent = state.stats.totalAnswered;
    const acc = state.stats.totalAnswered > 0 
      ? Math.round((state.stats.correctCount / state.stats.totalAnswered) * 100) 
      : 0;
    document.getElementById('stats-accuracy').textContent = `${acc}%`;
    document.getElementById('stats-best-streak').textContent = state.stats.bestStreak;
    document.getElementById('stats-bookmarked-count').textContent = state.stats.bookmarks.length;

    // Categories Progress
    const container = document.getElementById('category-progress-container');
    container.innerHTML = '';

    // Group all words by top category
    const catMap = {};
    state.allData.forEach(item => {
      const cat = item.category.split(' > ')[0];
      if (!catMap[cat]) catMap[cat] = { total: 0, mastered: 0 };
      catMap[cat].total += 1;
      if (state.stats.mastery[item.id] === 3) catMap[cat].mastered += 1;
    });

    Object.keys(catMap).sort().forEach(cat => {
      const info = catMap[cat];
      const percent = Math.round((info.mastered / info.total) * 100);
      const itemDiv = document.createElement('div');
      itemDiv.className = 'progress-item';
      itemDiv.innerHTML = `
        <div class="progress-meta">
          <span>${cat}</span>
          <span>${info.mastered} / ${info.total} (${percent}%)</span>
        </div>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" style="width: ${percent}%"></div>
        </div>
      `;
      container.appendChild(itemDiv);
    });
  }

  // ================= VIEW ROUTER =================
  function switchView(viewId) {
    state.currentView = viewId;
    
    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-view') === viewId);
    });

    document.querySelectorAll('.view-panel').forEach(panel => {
      panel.classList.toggle('active', panel.id === viewId);
      panel.classList.toggle('hidden', panel.id !== viewId);
    });

    // Show/hide quiz specific controls in toolbar
    const quizControls = document.getElementById('quiz-mode-controls');
    if (viewId === 'quiz-view') {
      quizControls.classList.remove('hidden');
    } else {
      quizControls.classList.add('hidden');
    }

    renderCurrentView();
  }

  function renderCurrentView() {
    if (state.currentView === 'quiz-view') {
      loadQuizQuestion();
    } else if (state.currentView === 'flashcard-view') {
      loadFlashcard();
    } else if (state.currentView === 'dict-view') {
      renderDictionary(document.getElementById('dict-search-input').value);
    } else if (state.currentView === 'stats-view') {
      renderStats();
    }
  }

  // ================= EVENT LISTENERS & SETUP =================
  function initEventListeners() {
    // Navigation
    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.addEventListener('click', () => switchView(btn.getAttribute('data-view')));
    });

    // Source Filter Pills
    document.querySelectorAll('.source-pills .pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.source-pills .pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.sourceFilter = btn.getAttribute('data-source');
        state.categoryFilter = 'all';
        applyFilters();
      });
    });

    // Category Select
    document.getElementById('category-select').addEventListener('change', (e) => {
      state.categoryFilter = e.target.value;
      applyFilters();
    });

    // Quiz Type Toggle (Typing vs Choice)
    document.querySelectorAll('.mode-pills .mode-pill-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-pills .mode-pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.quizType = btn.getAttribute('data-quiz-type');
        loadQuizQuestion();
      });
    });

    // Review Only Checkbox
    document.getElementById('filter-review-only').addEventListener('change', (e) => {
      state.reviewOnly = e.target.checked;
      applyFilters();
    });

    // Quiz Actions
    document.getElementById('quiz-typing-form').addEventListener('submit', handleTypingSubmit);
    document.getElementById('btn-hint-letter').addEventListener('click', revealLetterHint);
    document.getElementById('btn-reveal-answer').addEventListener('click', revealAnswerInstantly);
    document.getElementById('btn-next-quiz').addEventListener('click', nextQuizQuestion);
    document.getElementById('quiz-shuffle-btn').addEventListener('click', shuffleFilteredData);
    document.getElementById('quiz-bookmark-btn').addEventListener('click', toggleBookmark);

    // TTS Buttons
    document.getElementById('quiz-tts-btn').addEventListener('click', () => {
      if (state.currentWord && state.currentWord.examples && state.currentWord.examples.length > 0) {
        speakWord(state.currentWord.examples[0]);
      }
    });
    document.getElementById('feedback-tts-btn').addEventListener('click', () => {
      if (state.currentWord) speakWord(state.currentWord.word);
    });
    document.getElementById('fc-tts-btn').addEventListener('click', () => {
      const item = state.filteredData[state.currentIndex];
      if (item) speakWord(item.word);
    });

    // Flashcard Actions
    document.getElementById('flashcard-scene').addEventListener('click', flipFlashcard);
    document.getElementById('fc-shuffle-btn').addEventListener('click', shuffleFilteredData);
    document.querySelectorAll('.fc-rate-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        rateFlashcard(parseInt(btn.getAttribute('data-rating'), 10));
      });
    });

    // Dictionary Search
    const searchInput = document.getElementById('dict-search-input');
    const searchClear = document.getElementById('dict-search-clear');
    searchInput.addEventListener('input', (e) => {
      const val = e.target.value;
      searchClear.classList.toggle('hidden', !val);
      renderDictionary(val);
    });
    searchClear.addEventListener('click', () => {
      searchInput.value = '';
      searchClear.classList.add('hidden');
      renderDictionary('');
    });

    // Reset Stats
    document.getElementById('btn-reset-stats').addEventListener('click', () => {
      if (confirm('모든 누적 학습 통계와 오답 노트를 초기화하시겠습니까?')) {
        state.stats = {
          streak: 0,
          bestStreak: 0,
          xp: 0,
          totalAnswered: 0,
          correctCount: 0,
          wrongIds: [],
          bookmarks: [],
          mastery: {}
        };
        saveStats();
        renderStats();
        showToast('학습 기록이 초기화되었습니다.', 'info');
      }
    });

    // Sound & Theme Toggles
    const soundBtn = document.getElementById('sound-toggle-btn');
    soundBtn.addEventListener('click', () => {
      state.soundEnabled = !state.soundEnabled;
      const soundIcon = document.getElementById('sound-icon');
      soundIcon.setAttribute('data-lucide', state.soundEnabled ? 'volume-2' : 'volume-x');
      lucide.createIcons();
      showToast(state.soundEnabled ? '효과음 켜짐 🔊' : '효과음 꺼짐 🔇', 'info');
    });

    const themeBtn = document.getElementById('theme-toggle-btn');
    themeBtn.addEventListener('click', () => {
      state.theme = state.theme === 'dark' ? 'light' : 'dark';
      document.body.className = `${state.theme}-theme`;
      localStorage.setItem('vm_theme', state.theme);
      const themeIcon = document.getElementById('theme-icon');
      themeIcon.setAttribute('data-lucide', state.theme === 'dark' ? 'moon' : 'sun');
      lucide.createIcons();
    });

    // Global Keyboard Shortcuts
    window.addEventListener('keydown', (e) => {
      // Avoid hotkeys when typing in search or text inputs
      if (e.target === document.getElementById('dict-search-input')) return;

      if (state.currentView === 'quiz-view') {
        if (state.isAnswered && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          nextQuizQuestion();
        } else if (!state.isAnswered && state.quizType === 'choice' && ['1', '2', '3', '4'].includes(e.key)) {
          const idx = parseInt(e.key, 10) - 1;
          const choiceBtns = document.querySelectorAll('.choice-btn');
          if (choiceBtns[idx]) choiceBtns[idx].click();
        } else if (e.key === 'F2' || (e.ctrlKey && e.key === 'h')) {
          revealLetterHint();
        }
      } else if (state.currentView === 'flashcard-view') {
        if (e.key === ' ' || e.key === 'Enter') {
          e.preventDefault();
          flipFlashcard();
        } else if (['1', '2', '3'].includes(e.key)) {
          rateFlashcard(parseInt(e.key, 10));
        }
      }
    });
  }

  // Application Entry Point
  function initApp() {
    // Apply saved theme
    document.body.className = `${state.theme}-theme`;
    const themeIcon = document.getElementById('theme-icon');
    if (themeIcon) themeIcon.setAttribute('data-lucide', state.theme === 'dark' ? 'moon' : 'sun');

    updateHeaderStats();
    applyFilters();
    initEventListeners();
    lucide.createIcons();

    console.log(`VocabMaster initialized successfully with ${state.allData.length} words.`);
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
  } else {
    initApp();
  }

})();
