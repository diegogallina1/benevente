/**
 * Vercel Speed Insights initialization
 * This script initializes Speed Insights for static HTML pages
 * 
 * Based on @vercel/speed-insights package
 * Documentation: https://vercel.com/docs/speed-insights/quickstart
 */

(function() {
  'use strict';
  
  // Check if we're in production (Speed Insights doesn't track in development)
  var isDevelopment = window.location.hostname === 'localhost' || 
                      window.location.hostname === '127.0.0.1' ||
                      window.location.hostname.includes('local');
  
  if (isDevelopment) {
    console.log('[Speed Insights] Development mode detected - tracking disabled');
    return;
  }
  
  // Initialize the Speed Insights queue
  window.siq = window.siq || [];
  
  // Load the Speed Insights script
  var script = document.createElement('script');
  script.src = '/_vercel/speed-insights/script.js';
  script.defer = true;
  script.setAttribute('data-framework', 'vanilla');
  
  // Add error handling
  script.onerror = function() {
    console.warn('[Speed Insights] Failed to load script');
  };
  
  // Append script to document head
  if (document.head) {
    document.head.appendChild(script);
  } else {
    // Fallback if head is not available yet
    document.addEventListener('DOMContentLoaded', function() {
      document.head.appendChild(script);
    });
  }
  
  console.log('[Speed Insights] Initialized successfully');
})();
