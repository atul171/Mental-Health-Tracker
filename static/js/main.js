/**
 * Mental Health App - Main JavaScript
 */

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize all tooltips
    initTooltips();
    
    // Add active class to current nav item
    highlightCurrentNavItem();
    
    // Initialize any mood selectors on the page
    initMoodSelector();
    
    // Initialize meditation timer if on meditation page
    initMeditationTimer();
    
    // Initialize quiz functionality if on quiz page
    initQuiz();
    
    // Animate elements with data-animate attribute
    animateElements();
});

/**
 * Initialize Bootstrap tooltips
 */
function initTooltips() {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
}

/**
 * Highlight the current navigation item
 */
function highlightCurrentNavItem() {
    const currentPath = window.location.pathname;
    
    document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
}

/**
 * Initialize mood selector functionality
 */
function initMoodSelector() {
    const moodSelector = document.querySelector('.mood-selector');
    
    if (moodSelector) {
        const moodIcons = moodSelector.querySelectorAll('.mood-icon');
        
        moodIcons.forEach(icon => {
            icon.addEventListener('click', function() {
                // Remove selected class from all icons
                moodIcons.forEach(item => item.classList.remove('selected'));
                
                // Add selected class to clicked icon
                this.classList.add('selected');
                
                // Update hidden input value if it exists
                const moodInput = document.getElementById('selected_mood');
                if (moodInput) {
                    moodInput.value = this.dataset.mood;
                }
            });
        });
    }
}

/**
 * Initialize meditation timer
 */
function initMeditationTimer() {
    const timerDisplay = document.querySelector('.timer-display');
    const startButton = document.getElementById('start-timer');
    const pauseButton = document.getElementById('pause-timer');
    const resetButton = document.getElementById('reset-timer');
    
    if (timerDisplay && startButton) {
        let timer;
        let isRunning = false;
        let seconds = 0;
        
        // Format time as MM:SS
        function formatTime(totalSeconds) {
            const minutes = Math.floor(totalSeconds / 60);
            const seconds = totalSeconds % 60;
            return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
        
        // Update timer display
        function updateDisplay() {
            timerDisplay.textContent = formatTime(seconds);
        }
        
        // Start timer
        startButton.addEventListener('click', function() {
            if (!isRunning) {
                isRunning = true;
                timer = setInterval(function() {
                    seconds++;
                    updateDisplay();
                }, 1000);
                
                startButton.disabled = true;
                if (pauseButton) pauseButton.disabled = false;
            }
        });
        
        // Pause timer
        if (pauseButton) {
            pauseButton.addEventListener('click', function() {
                if (isRunning) {
                    isRunning = false;
                    clearInterval(timer);
                    startButton.disabled = false;
                    pauseButton.disabled = true;
                }
            });
        }
        
        // Reset timer
        if (resetButton) {
            resetButton.addEventListener('click', function() {
                isRunning = false;
                clearInterval(timer);
                seconds = 0;
                updateDisplay();
                startButton.disabled = false;
                if (pauseButton) pauseButton.disabled = true;
            });
        }
    }
}

/**
 * Initialize quiz functionality
 */
function initQuiz() {
    const quizContainer = document.querySelector('.quiz-container');
    
    if (quizContainer) {
        const nextButton = document.getElementById('next-question');
        const prevButton = document.getElementById('prev-question');
        const submitButton = document.getElementById('submit-quiz');
        const questionCards = document.querySelectorAll('.quiz-card');
        
        let currentQuestion = 0;
        
        // Show only the first question initially
        if (questionCards.length > 0) {
            updateQuestionVisibility();
        }
        
        // Update which question is visible
        function updateQuestionVisibility() {
            questionCards.forEach((card, index) => {
                if (index === currentQuestion) {
                    card.classList.remove('d-none');
                    card.classList.add('animated-fade-in');
                } else {
                    card.classList.add('d-none');
                    card.classList.remove('animated-fade-in');
                }
            });
            
            // Update button states
            if (prevButton) {
                prevButton.disabled = currentQuestion === 0;
            }
            
            if (nextButton) {
                nextButton.disabled = currentQuestion === questionCards.length - 1;
            }
            
            if (submitButton) {
                submitButton.style.display = currentQuestion === questionCards.length - 1 ? 'block' : 'none';
            }
        }
        
        // Next question button
        if (nextButton) {
            nextButton.addEventListener('click', function() {
                if (currentQuestion < questionCards.length - 1) {
                    currentQuestion++;
                    updateQuestionVisibility();
                }
            });
        }
        
        // Previous question button
        if (prevButton) {
            prevButton.addEventListener('click', function() {
                if (currentQuestion > 0) {
                    currentQuestion--;
                    updateQuestionVisibility();
                }
            });
        }
    }
}

/**
 * Animate elements with fade-in effect
 */
function animateElements() {
    const animatedElements = document.querySelectorAll('[data-animate]');
    
    if (animatedElements.length > 0) {
        // Set up Intersection Observer
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animated-fade-in');
                    // Stop watching once animation is applied
                    observer.unobserve(entry.target);
                }
            });
        });
        
        // Start observing elements
        animatedElements.forEach(element => {
            observer.observe(element);
        });
    }
} 