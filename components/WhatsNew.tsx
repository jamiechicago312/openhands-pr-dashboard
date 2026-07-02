'use client'

import { useState } from 'react'

interface WhatsNewProps {
  darkMode: boolean
}

export default function WhatsNew({ darkMode }: WhatsNewProps) {
  const [isHovered, setIsHovered] = useState(false)

  return (
    <div className="relative inline-block ml-3 hidden md:inline-block">
      <span
        className={`text-sm font-normal cursor-default select-none ${
          darkMode ? 'text-gray-400' : 'text-gray-500'
        } hover:${darkMode ? 'text-gray-300' : 'text-gray-600'} transition-colors`}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        ✨ What&apos;s New?
      </span>
      
      {isHovered && (
        <div className={`absolute top-full left-0 mt-2 w-80 p-4 rounded-lg shadow-lg border z-50 ${
          darkMode 
            ? 'bg-gray-800 border-gray-600 text-white' 
            : 'bg-white border-gray-200 text-gray-900'
        }`}>
          <div className="text-sm font-semibold mb-3 flex items-center">
            <span className="mr-2">✨</span>
            Latest Updates
          </div>
          <ul className="space-y-2 text-sm">
            <li className="flex items-start">
              <span className={`mr-2 mt-0.5 ${darkMode ? 'text-amber-400' : 'text-amber-600'}`}>•</span>
              <span>Static snapshot: data is frozen at 2026-07-01 21:58 UTC-5</span>
            </li>
            <li className="flex items-start">
              <span className={`mr-2 mt-0.5 ${darkMode ? 'text-blue-400' : 'text-blue-600'}`}>•</span>
              <span>Filters still work — they apply to the snapshot in memory</span>
            </li>
            <li className="flex items-start">
              <span className={`mr-2 mt-0.5 ${darkMode ? 'text-purple-400' : 'text-purple-600'}`}>•</span>
              <span>Auto-refresh is disabled (data never changes)</span>
            </li>
            <li className="flex items-start">
              <span className={`mr-2 mt-0.5 ${darkMode ? 'text-orange-400' : 'text-orange-600'}`}>•</span>
              <span>To regenerate, run <code className="px-1 py-0.5 rounded bg-gray-200 dark:bg-gray-700">npm run snapshot</code> with a GITHUB_TOKEN</span>
            </li>
          </ul>
        </div>
      )}
    </div>
  )
}