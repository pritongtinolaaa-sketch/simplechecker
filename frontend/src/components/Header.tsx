import React from 'react'

interface HeaderProps {
  onLogout?: () => void
  userName?: string
}

const Header: React.FC<HeaderProps> = ({ onLogout, userName }) => {
  return (
    <header className="header">
      <div className="header-content">
        <div className="header-main">
          <h1>🍪 Cookie Checker</h1>
          <p>Extract and analyze cookies from your browser or files</p>
        </div>
        <div className="header-user">
          {userName && <span className="user-name">Logged in as: <strong>{userName}</strong></span>}
          {onLogout && (
            <button className="logout-btn" onClick={onLogout}>
              🚪 Logout
            </button>
          )}
        </div>
      </div>
    </header>
  )
}

export default Header
