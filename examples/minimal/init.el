;;; -*- lexical-binding: t; -*-
;; The wrapper supplies the pinned manager before this configuration is loaded.
(require 'elpaca)
(let ((native-lock (expand-file-name "elpaca-lock.el" user-emacs-directory)))
  (when (file-exists-p native-lock)
    (setq elpaca-lock-file native-lock)
    (add-to-list 'elpaca-menu-functions 'elpaca-menu-lock-file)))
(setq purifier-answer 42)
(elpaca f
  (require 'f)
  (unless (equal (f-filename (format "/fixture/%s" purifier-answer))
                 (number-to-string purifier-answer))
    (error "Native f API failed")))
(add-hook 'after-init-hook #'elpaca-process-queues)
