import React from 'react'
import Icon from './Icon'

const Header: React.FC = () => {
  return (
    <header className="header">
      <div className="header-content">
        <div className="header-main">
          <h1>
            <Icon name="cookie" size={38} className="header-cookie-icon" />
            <span>Cookie Checker</span>
          </h1>
          <p>Extract and analyze cookies from your browser or files</p>
        </div>
      </div>
    </header>
  )
}

export default Header
