import React from 'react'
import Icon from './Icon'

const Header: React.FC<{ isAdmin?: boolean }> = ({ isAdmin = false }) => {
  return (
    <header className="header">
      <div className="header-content">
        <div className="header-main">
          <h1>
            <Icon name="cookie" size={38} className="header-cookie-icon" />
            <span>Cookie Checker</span>
          </h1>
          <span className="header-credit">by Schiro</span>
          <p className="header-subtitle">Extract and analyze cookies from your browser or files</p>
        </div>
      </div>
      {isAdmin && (
        <span className="header-admin-status">
          <span className="header-admin-dot" />
          Admin logged in
        </span>
      )}
    </header>
  )
}

export default Header
