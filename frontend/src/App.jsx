import { useState } from 'react'
import StudentView from './pages/StudentView.jsx'
import TeacherView from './pages/TeacherView.jsx'

export default function App() {
  const [tab, setTab] = useState('student')

  return (
    <>
      <nav className="nav">
        <span className="nav-brand">⚡ Socratic Spark</span>
        <div className="nav-tabs">
          <button
            className={`nav-tab ${tab === 'student' ? 'active' : ''}`}
            onClick={() => setTab('student')}
          >
            Student
          </button>
          <button
            className={`nav-tab ${tab === 'teacher' ? 'active' : ''}`}
            onClick={() => setTab('teacher')}
          >
            Teacher
          </button>
        </div>
      </nav>
      {tab === 'student' ? <StudentView /> : <TeacherView />}
    </>
  )
}
