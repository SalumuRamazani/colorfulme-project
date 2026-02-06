// Lazy-load external libraries for fast page load
const scriptCache = {};
async function loadScript(url) {
    if (scriptCache[url]) return scriptCache[url];
    
    scriptCache[url] = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = url;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error(`Failed to load ${url}`));
        document.head.appendChild(script);
    });
    
    return scriptCache[url];
}

// Global counter for unique item IDs (ensures uniqueness even in same millisecond)
let itemIdCounter = 0;

// Helper function to ensure all items in a section have unique IDs
function ensureItemIds(items) {
    if (!items || !Array.isArray(items)) return items;
    return items.map((item, index) => {
        if (!item.id) {
            itemIdCounter++;
            item.id = 'item_' + Date.now() + '_' + itemIdCounter + '_' + index;
        }
        return item;
    });
}

// Section Registry - Defines all available section types
const sectionRegistry = {
    settings: {
        id: 'settings',
        name: 'Settings',
        icon: 'settings',
        maxInstances: 1,
        allowMultiple: false,
        hasDivider: false,
        defaultData: {
            currencySymbol: '$',
            currencyPosition: 'before',
            selectedFont: 'font-1',
            textColor: '#000000',
            showBackground: true,
            receiptWidth: 320
        }
    },
    header: {
        id: 'header',
        name: 'Header',
        icon: 'header',
        maxInstances: 1,
        allowMultiple: false,
        hasDivider: true,
        defaultData: {
            logoUrl: '',
            headerAlignment: 'center',
            logoSize: 50,
            businessName: 'Business Details',
            headerDivider: '---',
            showHeaderDivider: true
        }
    },
    dateTime: {
        id: 'dateTime',
        name: 'Date & Time',
        icon: 'calendar',
        maxInstances: 1,
        allowMultiple: false,
        hasDivider: true,
        defaultData: {
            dateAlignment: 'left',
            dateTime: '',
            dateDivider: '---',
            showDateDivider: true
        }
    },
    twoColumn: {
        id: 'twoColumn',
        name: 'Two column information',
        icon: 'columns',
        maxInstances: 10,
        allowMultiple: true,
        hasDivider: true,
        defaultData: {
            customFields: [
                { label: 'Table', value: '415', column: 1 },
                { label: 'Server', value: 'Rebecca', column: 1 },
                { label: 'Guests', value: '2', column: 2 }
            ],
            infoDivider: '---',
            showInfoDivider: true
        }
    },
    items: {
        id: 'items',
        name: 'Items list',
        icon: 'cart',
        maxInstances: 1,
        allowMultiple: false,
        hasDivider: true,
        defaultData: {
            items: [
                { id: 'item_' + Date.now() + '_1', quantity: 1, name: 'Americano', price: 2.99 },
                { id: 'item_' + Date.now() + '_2', quantity: 2, name: 'Chocolate Chip Cookie', price: 1.98 },
                { id: 'item_' + Date.now() + '_3', quantity: 2, name: 'Coke', price: 1.5 }
            ],
            itemsDivider: '---',
            showItemsDivider: true
        }
    },
    payment: {
        id: 'payment',
        name: 'Payment',
        icon: 'payment',
        maxInstances: 1,
        allowMultiple: false,
        hasDivider: true,
        defaultData: {
            taxRate: null,
            showTaxRate: false,
            paymentType: 'cash',
            paymentFields: [],
            paymentDivider: '---',
            showPaymentDivider: true
        }
    },
    customMessage: {
        id: 'customMessage',
        name: 'Custom message',
        icon: 'message',
        maxInstances: 10,
        allowMultiple: true,
        hasDivider: true,
        defaultData: {
            customMessage: 'THANK YOU\nHAVE A NICE DAY',
            messageAlignment: 'center',
            messageBold: false,
            messageDivider: '---',
            showMessageDivider: false
        }
    },
    barcode: {
        id: 'barcode',
        name: 'Barcode',
        icon: 'barcode',
        maxInstances: 1,
        allowMultiple: false,
        hasDivider: false,
        defaultData: {
            barcodeEnabled: true,
            barcodeSize: 50,
            barcodeLength: 50,
            barcodeValue: ''
        }
    }
};

// Advanced Receipt Generator V2 - Modular Section System
function advancedReceiptGeneratorV2(hasSubscription = false, templateConfig = null, isAuthenticated = false, templateName = '') {
    return {
        // Core state
        sections: [],
        nextInstanceId: 1,
        sectionRegistry: sectionRegistry,
        addSectionModalOpen: false,
        hasSubscription: Boolean(hasSubscription),
        templateConfig: templateConfig,
        isAuthenticated: Boolean(isAuthenticated),
        templateName: templateName,
        
        // Drag and drop state
        draggedId: null,
        draggedOverId: null,
        
        // Save template modal state
        showSaveTemplateModal: false,
        saveTemplateName: '',
        saveTemplateDescription: '',
        saveTemplateError: '',
        saveTemplateSuccess: false,
        saveTemplateLoading: false,
        hasPendingSave: false,
        showAutoSaveSuccess: false,
        
        // Preview visibility for mobile
        showPreview: false,
        
        // Download state
        downloadingPdf: false,
        downloadSuccessToast: false,
        downloadJustCompleted: false,
        showDownloadMenu: false,
        downloadingFormat: null,
        
        // Auto-save state
        autoSaveNotification: false,
        lastAutoSave: null,
        autoSaveTimer: null,
        autoSaveDebounceTimer: null, // For debounced auto-save on changes
        
        // Post-login redirect state
        checkPostLoginRedirect() {
            // Check if user just logged in with a template save intent
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('redirect_to_dashboard') === '1') {
                // Check if backend auto-saved the template
                const pageHasSuccessFlag = document.body.getAttribute('data-autosave-success') === 'true';
                if (pageHasSuccessFlag) {
                    // Wait a moment then redirect to dashboard
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 500);
                }
            }
        },
        autoSaveKey: null, // Template-specific auto-save key
        hasRestoredFromAutoSave: false, // Flag to prevent default sections overwriting restored data
        savedTemplateSlug: '', // Slug of the template that was auto-saved (for comparison)
        
        // Restore modal state (shown when returning user has saved work)
        showRestoreModal: false,
        pendingRestoreConfig: null, // Stores the config to restore if user clicks Continue
        
        // Reactive receipt width (updated from watch for guaranteed reactivity)
        currentReceiptWidth: 320,
        
        // Preview update debouncing (Week 3.1)
        previewUpdating: false,
        updateDebounceTimer: null,
        debouncedSections: [],
        hasTrackedFirstEdit: false,
        
        // Generate template-specific auto-save key based on current URL
        getAutoSaveKey() {
            const path = window.location.pathname;
            // Extract template name from URL like /generate-walmart-receipt or /generate-advanced
            const cleanPath = path.replace(/\//g, '_').replace(/-/g, '_');
            return 'receipt_autosave' + cleanPath;
        },
        
        // Extract template slug from URL for comparison (e.g., 'walmart' from '/generate-walmart-receipt')
        getTemplateSlugFromUrl() {
            const path = window.location.pathname;
            // Match patterns like /generate-walmart-receipt, /generate-target-receipt, etc.
            const match = path.match(/\/generate-([^-]+(?:-[^-]+)*)-receipt/);
            if (match) {
                return match[1]; // e.g., 'walmart', 'best-buy', 'cvs-pharmacy'
            }
            // For /generate-advanced, return 'advanced' or empty string
            if (path.includes('/generate-advanced')) {
                return 'advanced';
            }
            return '';
        },
        
        // Initialize with default or template sections
        init() {
            // Store reference for fixed header access
            window.receiptGenerator = this;
            
            // Initialize template-specific auto-save key
            this.autoSaveKey = this.getAutoSaveKey();
            
            // Listen for store-template-for-save event from login modal
            window.addEventListener('store-template-for-save', () => {
                this.storeTemplateForSave();
            });
            
            // Check for saved receipt in localStorage
            this.checkForSavedReceipt();
            
            // If loading a template via query parameter (from dashboard), clear any old pending saves
            // This prevents unwanted auto-redirects from abandoned flows
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.has('load_template')) {
                sessionStorage.removeItem('pending_template_save');
            }
            
            this.checkPendingTemplateSave();
            
            // Check if user just logged in with a template save intent and redirect to dashboard if auto-saved
            this.checkPostLoginRedirect();
            
            // Initialize sections based on context (pending save, template, or defaults)
            // If restore modal is shown, load the saved receipt so user can see what they're restoring
            if (this.hasPendingSave) {
                // Pending save already loaded sections via checkPendingTemplateSave
                // Just start auto-save and skip default initialization
            } else if (this.showRestoreModal && this.pendingRestoreConfig) {
                // Banner is shown - load the saved receipt so user can SEE it
                // They can then choose to keep it or start fresh
                console.log('Loading saved receipt for preview - banner shown');
                this.loadTemplate(this.pendingRestoreConfig);
                this.hasRestoredFromAutoSave = true;
            } else if (this.templateConfig) {
                // No saved data, load the explicit template configuration
                console.log('Loading template:', this.templateName || 'custom');
                this.loadTemplate(this.templateConfig);
            } else {
                // No saved data and no template - load defaults
                // Create default sections with pre-filled example data for instant usability
                // Create Settings section first (allows font/color/currency customization)
                const settingsSection = this.createSection('settings', true);
                settingsSection.data.selectedFont = 'font-1';
                settingsSection.data.textColor = '#000000';
                settingsSection.data.currencyFormat = '$X';
                settingsSection.data.receiptWidth = 320;
                
                const headerSection = this.createSection('header', true); // collapsed for mobile UX
                // Add a simple black and white SVG logo as base64 data URL
                headerSection.data.logoUrl = 'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 80 80"><circle cx="40" cy="40" r="35" fill="#000000" stroke="#333333" stroke-width="2"/><text x="40" y="50" font-family="Arial" font-size="32" font-weight="bold" fill="#ffffff" text-anchor="middle">SE</text></svg>');
                headerSection.data.logoSize = 35;
                headerSection.data.businessName = 'STORE EXPRESS';
                headerSection.data.line1 = '123 Main Street';
                headerSection.data.line2 = 'Springfield, IL 62701';
                headerSection.data.line3 = '(555) 123-4567';
                headerSection.data.headerAlignment = 'center';
                
                const dateTimeSection = this.createSection('dateTime', true);
                dateTimeSection.data.dateTime = new Date().toLocaleString('en-US', {
                    month: '2-digit',
                    day: '2-digit', 
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                    hour12: true
                });
                dateTimeSection.data.dateAlignment = 'center';
                
                const itemsSection = this.createSection('items', false); // open by default so users understand items list
                itemsSection.data.items = [
                    { id: 'item_1', quantity: 2, name: 'Wireless Mouse', price: 24.99 },
                    { id: 'item_2', quantity: 1, name: 'USB-C Cable (6ft)', price: 12.99 },
                    { id: 'item_3', quantity: 1, name: 'Phone Screen Protector', price: 9.99 },
                    { id: 'item_4', quantity: 3, name: 'AA Batteries (4-pack)', price: 8.99 }
                ];
                
                const paymentSection = this.createSection('payment', true);
                paymentSection.data.taxRate = 8.5;
                paymentSection.data.showTaxRate = true;
                paymentSection.data.paymentType = 'card';
                paymentSection.data.paymentFields = [
                    { label: 'Card number', value: '**** **** **** 4922' },
                    { label: 'Card type', value: 'Debit' },
                    { label: 'Card entry', value: 'Chip' },
                    { label: 'Transaction #', value: '458721' },
                    { label: 'Cashier', value: 'Sarah M.' },
                    { label: 'Register', value: '03' },
                    { label: 'REWARDS MEMBER', value: '#SE892341' },
                    { label: 'Points earned', value: '45' },
                    { label: 'Total points', value: '1,245' }
                ];
                
                const messageSection = this.createSection('customMessage', true);
                messageSection.data.customMessage = 'Thank you for shopping with us!\n\nReturns accepted within 30 days with receipt.\nFor assistance, call us at (555) 123-4567';
                messageSection.data.messageAlignment = 'center';
                
                // Add promotional message section
                const promoSection = this.createSection('customMessage', true);
                promoSection.data.customMessage = 'Visit us online at StoreExpress.com for exclusive deals!\n\nSign up for our rewards program and earn 1 point per dollar spent. New members get 500 bonus points!\n\nJoin our email list for 10% off your next purchase.\n\nFollow us @StoreExpress on social media for daily deals, giveaways, and special promotions.\n\nShop with confidence - 100% satisfaction guaranteed or your money back.';
                promoSection.data.messageAlignment = 'center';
                
                const barcodeSection = this.createSection('barcode', true);
                barcodeSection.data.barcodeValue = '458721';
                
                this.sections = [
                    settingsSection,
                    headerSection,
                    dateTimeSection,
                    itemsSection,
                    paymentSection,
                    messageSection,
                    promoSection,
                    barcodeSection
                ];
            }
            
            // Start auto-save timer (every 10 seconds) - runs for ALL init paths
            this.startAutoSave();
            
            // Initialize debounced sections with current sections (MUST run for all paths)
            // Use $nextTick to ensure sections are fully populated before cloning
            this.$nextTick(() => {
                this.debouncedSections = JSON.parse(JSON.stringify(this.sections));
            });
            
            // Watch for changes to sections (deep watch via JSON serialization) - Week 3.1
            // Alpine's $watch doesn't deep-watch by default, so we serialize to catch nested mutations
            // MUST run for all paths including pending save recovery
            this.$watch(() => JSON.stringify(this.sections), () => {
                this.triggerDebouncedPreviewUpdate();
                // Also trigger debounced auto-save on every change
                this.triggerDebouncedAutoSave();
                // Update the reactive receiptWidth property for preview binding
                const settings = this.sections.find(s => s.type === 'settings');
                if (settings) {
                    this.currentReceiptWidth = settings.data.receiptWidth || 320;
                }
            });
            
            // CRITICAL: Save receipt before user leaves the page
            window.addEventListener('beforeunload', () => {
                console.log('⚠️ User is leaving page - forcing auto-save');
                // Force immediate save before page unload (localStorage.setItem is synchronous)
                this.autoSave();
                
                // Clean up timers
                if (this.autoSaveTimer) {
                    clearInterval(this.autoSaveTimer);
                }
                if (this.updateDebounceTimer) {
                    clearTimeout(this.updateDebounceTimer);
                }
                if (this.autoSaveDebounceTimer) {
                    clearTimeout(this.autoSaveDebounceTimer);
                }
            });
            
            // Also save on page visibility change (user switches tabs)
            document.addEventListener('visibilitychange', () => {
                if (document.hidden) {
                    console.log('📱 Tab hidden - forcing auto-save');
                    this.autoSave();
                }
            });
            
            // Render barcodes after page loads (with delay to ensure DOM is ready)
            setTimeout(() => {
                this.renderBarcodes();
            }, 500);
        },
        
        // Debounced preview update (Week 3.1)
        triggerDebouncedPreviewUpdate() {
            // Show loading state immediately
            this.previewUpdating = true;
            
            // Clear any existing debounce timer
            if (this.updateDebounceTimer) {
                clearTimeout(this.updateDebounceTimer);
            }
            
            // Set new debounce timer (300ms delay)
            this.updateDebounceTimer = setTimeout(() => {
                // Deep clone sections to debouncedSections for preview rendering
                this.debouncedSections = JSON.parse(JSON.stringify(this.sections));
                
                // Hide loading state
                this.previewUpdating = false;
                
                // Re-render barcodes after preview updates
                this.renderBarcodes();
                
                // Track first field edit for analytics
                if (window.posthog && !this.hasTrackedFirstEdit) {
                    posthog.capture('first_field_edited');
                    this.hasTrackedFirstEdit = true;
                }
            }, 300);
        },
        
        // Load template configuration
        loadTemplate(config) {
            this.sections = [];
            
            // Check if config uses new sections array format (Target template)
            if (config.sections && Array.isArray(config.sections)) {
                // New format with sections array
                // First add settings if present
                if (config.settings) {
                    const settingsSection = this.createSection('settings');
                    Object.assign(settingsSection.data, config.settings);
                    this.sections.push(settingsSection);
                }
                
                // Add header if present
                if (config.header) {
                    const headerSection = this.createSection('header');
                    Object.assign(headerSection.data, config.header);
                    this.sections.push(headerSection);
                }
                
                // Process sections array
                config.sections.forEach(sectionConfig => {
                    const section = this.createSection(sectionConfig.type);
                    if (section && sectionConfig.data) {
                        Object.assign(section.data, sectionConfig.data);
                        
                        // Ensure items have unique IDs
                        if (section.type === 'items' && section.data.items) {
                            section.data.items = ensureItemIds(section.data.items);
                        }
                        
                        this.sections.push(section);
                    }
                });
            } else {
                // Old format (Starbucks template)
                // Settings section
                if (config.settings) {
                    const settingsSection = this.createSection('settings');
                    Object.assign(settingsSection.data, config.settings);
                    this.sections.push(settingsSection);
                }
                
                // Header section
                if (config.header) {
                    const headerSection = this.createSection('header');
                    Object.assign(headerSection.data, config.header);
                    this.sections.push(headerSection);
                }
                
                // DateTime section
                if (config.dateTime) {
                    const dateTimeSection = this.createSection('dateTime');
                    Object.assign(dateTimeSection.data, config.dateTime);
                    this.sections.push(dateTimeSection);
                }
                
                // TwoColumn section(s)
                if (config.twoColumn && config.twoColumn.length > 0) {
                    const twoColSection = this.createSection('twoColumn');
                    // Map config items to customFields format with column property
                    twoColSection.data.customFields = config.twoColumn.map((item, index) => ({
                        label: item.label,
                        value: item.value,
                        column: 1  // All items in column 1 for simple list format
                    }));
                    this.sections.push(twoColSection);
                }
                
                // Custom messages before items
                if (config.customMessages && config.customMessages.length > 0) {
                    config.customMessages.forEach(msg => {
                        const msgSection = this.createSection('customMessage');
                        Object.assign(msgSection.data, msg);
                        this.sections.push(msgSection);
                    });
                }
            
            // Items section
            if (config.items && config.items.length > 0) {
                const itemsSection2 = this.createSection('items');
                itemsSection2.data.items = ensureItemIds(config.items.map((item) => ({
                    ...item,
                    name: item.name,
                    price: String(item.price),
                    quantity: item.quantity || '',
                    indent: item.indent || false
                })));
                this.sections.push(itemsSection2);
            }
            
            // Payment section
            if (config.payment) {
                const paymentSection2 = this.createSection('payment');
                Object.assign(paymentSection2.data, config.payment);
                this.sections.push(paymentSection2);
            }
            
            // Custom messages after payment (date/time only, before barcode)
            if (config.customMessages2 && config.customMessages2.length > 0 && config.customMessages2[0]) {
                const dateTimeMsg = this.createSection('customMessage');
                Object.assign(dateTimeMsg.data, config.customMessages2[0]);
                this.sections.push(dateTimeMsg);
            }
            
            // Barcode section
            if (config.barcode) {
                const barcodeSection = this.createSection('barcode');
                Object.assign(barcodeSection.data, config.barcode);
                this.sections.push(barcodeSection);
            }
            
            // Barcode number and thank you message (after barcode)
            if (config.customMessages2 && config.customMessages2.length > 1) {
                for (let i = 1; i < config.customMessages2.length; i++) {
                    const msgSection = this.createSection('customMessage');
                    Object.assign(msgSection.data, config.customMessages2[i]);
                    this.sections.push(msgSection);
                }
            }
            }  // Close the else block for old format
            
            // Final safety pass: ensure ALL items in ALL sections have unique IDs
            this.sections.forEach(section => {
                if (section.type === 'items' && section.data.items) {
                    section.data.items = ensureItemIds(section.data.items);
                }
            });
            
            // CRITICAL: Migrate settings section to ensure receiptWidth exists
            // Old autosaves may not have this property, and Alpine needs it to be defined for reactivity
            const settingsSection = this.sections.find(s => s.type === 'settings');
            if (settingsSection) {
                if (settingsSection.data.receiptWidth == null) {
                    settingsSection.data.receiptWidth = 320;
                    console.log('Migrated: added receiptWidth to settings');
                }
                // Update the reactive currentReceiptWidth property
                this.currentReceiptWidth = settingsSection.data.receiptWidth;
            }
            
            console.log('Template loaded:', this.sections.length, 'sections');
        },
        
        // Create a new section instance
        createSection(type, collapsed = true) {
            const template = this.sectionRegistry[type];
            if (!template) {
                console.error('Unknown section type:', type);
                return null;
            }
            
            return {
                instanceId: this.nextInstanceId++,
                type: type,
                collapsed: collapsed,
                data: JSON.parse(JSON.stringify(template.defaultData))
            };
        },
        
        // Add a new section
        addSection(type) {
            const template = this.sectionRegistry[type];
            if (!template) return;
            
            // Check if max instances reached
            const currentCount = this.sections.filter(s => s.type === type).length;
            if (currentCount >= template.maxInstances) {
                alert(`Maximum ${template.maxInstances} ${template.name} section(s) allowed`);
                return;
            }
            
            const newSection = this.createSection(type, false);
            this.sections.push(newSection);
            this.addSectionModalOpen = false;
        },
        
        // Remove a section
        removeSection(instanceId) {
            const section = this.sections.find(s => s.instanceId === instanceId);
            if (!section) return;
            
            // Warn before removing core singleton sections
            const coreTypes = ['settings', 'items', 'payment'];
            if (coreTypes.includes(section.type)) {
                if (!confirm(`Are you sure you want to remove the ${this.getSectionTemplate(section.type).name} section? This may affect your receipt.`)) {
                    return;
                }
            }
            
            const index = this.sections.findIndex(s => s.instanceId === instanceId);
            if (index > -1) {
                this.sections.splice(index, 1);
            }
        },
        
        // Toggle section collapse
        toggleSection(instanceId) {
            const section = this.sections.find(s => s.instanceId === instanceId);
            if (section) {
                section.collapsed = !section.collapsed;
            }
        },
        
        // Move section up
        moveSectionUp(instanceId) {
            const currentIndex = this.sections.findIndex(s => s.instanceId === instanceId);
            if (currentIndex <= 0) return; // Already at top
            
            // Swap with previous section
            const temp = this.sections[currentIndex];
            this.sections[currentIndex] = this.sections[currentIndex - 1];
            this.sections[currentIndex - 1] = temp;
            
            // Force reactivity
            this.sections = [...this.sections];
        },
        
        // Move section down
        moveSectionDown(instanceId) {
            const currentIndex = this.sections.findIndex(s => s.instanceId === instanceId);
            if (currentIndex < 0 || currentIndex >= this.sections.length - 1) return; // Already at bottom
            
            // Swap with next section
            const temp = this.sections[currentIndex];
            this.sections[currentIndex] = this.sections[currentIndex + 1];
            this.sections[currentIndex + 1] = temp;
            
            // Force reactivity
            this.sections = [...this.sections];
        },
        
        // Track which element should allow dragging
        dragHandleActive: false,
        isDraggingNow: false,
        isMobile: window.innerWidth < 1024,
        
        // Haptic feedback helper
        vibrate(duration) {
            if (navigator.vibrate) {
                navigator.vibrate(duration);
            }
        },
        
        // Drag and drop methods
        handleDragStart(event, section) {
            this.dragHandleActive = true;
            this.isDraggingNow = true;
        },
        
        dragStartFromHandle(event, section) {
            // Prevent drag when interacting with form controls (inputs, sliders, selects, etc.)
            const tagName = event.target.tagName.toLowerCase();
            const interactiveElements = ['input', 'select', 'textarea', 'button', 'label'];
            if (interactiveElements.includes(tagName)) {
                event.preventDefault();
                return;
            }
            
            // Also check if parent is an interactive element (for nested elements like slider thumbs)
            if (event.target.closest('input, select, textarea, button, label')) {
                event.preventDefault();
                return;
            }
            
            this.draggedId = section.instanceId;
            this.isDraggingNow = true;
            event.dataTransfer.effectAllowed = 'move';
            
            // Haptic feedback on drag start
            if (navigator.vibrate) {
                navigator.vibrate(50);
            }
        },
        
        dragOver(event, targetSection) {
            if (!this.draggedId || !targetSection) return;
            
            // Only update if we're over a different section
            if (this.draggedOverId !== targetSection.instanceId) {
                this.draggedOverId = targetSection.instanceId;
                
                // Only reorder if target is different from dragged
                if (this.draggedId !== targetSection.instanceId) {
                    const draggedIndex = this.sections.findIndex(s => s.instanceId === this.draggedId);
                    const targetIndex = this.sections.findIndex(s => s.instanceId === targetSection.instanceId);
                    
                    if (draggedIndex !== -1 && targetIndex !== -1 && draggedIndex !== targetIndex) {
                        // Perform swap
                        const draggedSection = this.sections[draggedIndex];
                        this.sections.splice(draggedIndex, 1);
                        this.sections.splice(targetIndex, 0, draggedSection);
                        this.sections = [...this.sections];
                    }
                }
            }
            
            event.dataTransfer.dropEffect = 'move';
            event.preventDefault();
        },
        
        dragLeave() {
            this.draggedOverId = null;
        },
        
        dragDrop(event, targetSection) {
            event.preventDefault();
            
            if (!this.draggedId || !targetSection) {
                this.draggedId = null;
                this.draggedOverId = null;
                return;
            }
            
            // Haptic feedback on drop
            if (navigator.vibrate) {
                navigator.vibrate([30, 50, 30]);
            }
            
            // Finalize the drop
            this.draggedId = null;
            this.draggedOverId = null;
        },
        
        dragEnd(event) {
            this.draggedId = null;
            this.draggedOverId = null;
            // Use setTimeout to batch the isDraggingNow reset for better performance
            requestAnimationFrame(() => {
                this.isDraggingNow = false;
            });
            
            // Haptic feedback on drag end
            if (navigator.vibrate) {
                navigator.vibrate(30);
            }
        },
        
        // Get section template
        getSectionTemplate(type) {
            return this.sectionRegistry[type];
        },
        
        // Check if section type can be added
        canAddSection(type) {
            const template = this.sectionRegistry[type];
            if (!template) return false;
            
            const currentCount = this.sections.filter(s => s.type === type).length;
            return currentCount < template.maxInstances;
        },
        
        // Get global settings (from settings section)
        get globalSettings() {
            const settingsSection = this.sections.find(s => s.type === 'settings');
            return settingsSection ? settingsSection.data : {
                currencyFormat: '$X',
                selectedFont: 'font-1',
                textColor: '#000000',
                showBackground: true,
                receiptWidth: 320
            };
        },
        
        // Computed: Subtotal (from items sections)
        get subtotal() {
            return this.sections
                .filter(s => s.type === 'items')
                .reduce((total, section) => {
                    return total + section.data.items.reduce((sum, item) => {
                        return sum + (parseFloat(item.price) || 0) * (parseInt(item.quantity) || 0);
                    }, 0);
                }, 0);
        },
        
        // Computed: Tax
        get tax() {
            const paymentSection = this.sections.find(s => s.type === 'payment');
            const taxRate = paymentSection ? (parseFloat(paymentSection.data.taxRate) || 0) : 0;
            // Only calculate tax if tax rate is enabled and greater than 0
            if (paymentSection && paymentSection.data.showTaxRate && taxRate > 0) {
                return this.subtotal * (taxRate / 100);
            }
            return 0;
        },
        
        // Computed: Total
        get total() {
            const paymentSection = this.sections.find(s => s.type === 'payment');
            const taxRate = paymentSection ? (parseFloat(paymentSection.data.taxRate) || 0) : 0;
            // Only add tax if tax rate is enabled and greater than 0
            if (paymentSection && paymentSection.data.showTaxRate && taxRate > 0) {
                return this.subtotal + this.tax;
            }
            return this.subtotal;
        },
        
        // Format currency based on position (before, after, after-space)
        formatCurrency(amount) {
            const settings = this.globalSettings;
            const symbol = settings.currencySymbol ?? '$';
            const position = settings.currencyPosition || 'before';
            const formatted = amount.toFixed(2);
            
            if (!symbol || symbol.trim() === '') {
                return formatted;
            }
            
            switch(position) {
                case 'before':
                    return symbol + formatted;
                case 'after':
                    return formatted + symbol;
                case 'after-space':
                    return formatted + ' ' + symbol;
                default:
                    return symbol + formatted;
            }
        },
        
        // Alias for formatCurrency (used in login modal preview)
        formatPrice(amount) {
            return this.formatCurrency(amount);
        },
        
        // Calculate subtotal (used in login modal preview)
        calculateSubtotal() {
            return this.subtotal;
        },
        
        // Get divider - dynamically sized based on receipt width
        getDivider(style) {
            // Calculate character count based on receipt width
            // Receipt has p-8 padding (32px each side = 64px total)
            // Monospace font character width is approximately 0.6 * font-size
            // Use smaller divisor to ensure divider fills width (overflow hidden will clip excess)
            const receiptWidth = this.currentReceiptWidth || 320;
            const contentWidth = receiptWidth - 64; // subtract padding
            const charWidth = 6; // slightly smaller to ensure full coverage
            const charCount = Math.max(15, Math.ceil(contentWidth / charWidth) + 2); // add buffer
            
            const patterns = {
                '---': '-',
                '===': '=',
                '...': '.',
                ':::': ':',
                '***': '*'
            };
            const char = patterns[style] || '-';
            return char.repeat(charCount);
        },
        
        // Generate barcode (length determines number of digits)
        generateBarcode(length = 50) {
            // Number of digits based on length slider (10-100 → 1-10 digits)
            const numDigits = Math.floor(length / 10);
            let code = '';
            // Generate random digits for uniqueness
            for (let i = 0; i < numDigits; i++) {
                code += Math.floor(Math.random() * 10);
            }
            return code || '0';
        },
        
        // Get or generate barcode value for a section
        getBarcodeValue(section) {
            // If barcodeValue exists and is not empty, use it
            if (section.data.barcodeValue) {
                return section.data.barcodeValue;
            }
            // Otherwise generate and store new value
            const newValue = this.generateBarcode(section.data.barcodeLength || 50);
            section.data.barcodeValue = newValue;
            return newValue;
        },
        
        // Refresh barcode value (generate new one)
        refreshBarcode(sectionId) {
            const section = this.sections.find(s => s.instanceId === sectionId);
            if (section && section.type === 'barcode') {
                section.data.barcodeValue = this.generateBarcode(section.data.barcodeLength || 50);
                // Re-render barcodes after value change
                this.renderBarcodes();
            }
        },
        
        // Render all barcode SVG elements using JsBarcode
        renderBarcodes() {
            // Wait for DOM to be ready
            setTimeout(() => {
                if (typeof JsBarcode === 'undefined') {
                    console.warn('JsBarcode not loaded yet');
                    return;
                }
                
                // Find all barcode SVG elements
                const barcodeSvgs = document.querySelectorAll('svg[id^="barcode-"]');
                
                barcodeSvgs.forEach(svg => {
                    // Get the barcode value from the sibling text element
                    const valueEl = svg.parentElement?.querySelector('.text-center.text-xs');
                    const barcodeValue = valueEl ? valueEl.textContent.trim() : '0';
                    
                    // Get height from section data (parse from parent style or use default)
                    const section = this.sections.find(s => svg.id === `barcode-${s.instanceId}`);
                    const height = section?.data?.barcodeSize || 50;
                    
                    try {
                        JsBarcode(`#${svg.id}`, barcodeValue, {
                            format: 'CODE128',
                            width: 2,
                            height: parseInt(height),
                            displayValue: false,
                            margin: 0,
                            background: '#ffffff',
                            lineColor: '#000000'
                        });
                    } catch (e) {
                        console.error('JsBarcode render error for', svg.id, ':', e);
                    }
                });
            }, 100);
        },
        
        // Section-specific methods
        addItem(sectionId) {
            const section = this.sections.find(s => s.instanceId === sectionId);
            if (section && section.type === 'items') {
                // Generate unique ID for the item using timestamp and random string
                const uniqueId = 'item_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
                section.data.items.push({ id: uniqueId, quantity: 1, name: '', price: 0 });
            }
        },
        
        removeItem(sectionId, index) {
            const section = this.sections.find(s => s.instanceId === sectionId);
            if (section && section.type === 'items') {
                section.data.items.splice(index, 1);
            }
        },
        
        addCustomField(sectionId, column = 1) {
            const section = this.sections.find(s => s.instanceId === sectionId);
            if (section && section.type === 'twoColumn') {
                section.data.customFields.push({ label: '', value: '', column });
            }
        },
        
        removeCustomField(sectionId, index) {
            const section = this.sections.find(s => s.instanceId === sectionId);
            if (section && section.type === 'twoColumn') {
                section.data.customFields.splice(index, 1);
            }
        },
        
        addPaymentField(sectionId) {
            const section = this.sections.find(s => s.instanceId === sectionId);
            if (section && section.type === 'payment') {
                section.data.paymentFields.push({ label: '', value: '' });
            }
        },
        
        removePaymentField(sectionId, index) {
            const section = this.sections.find(s => s.instanceId === sectionId);
            if (section && section.type === 'payment') {
                section.data.paymentFields.splice(index, 1);
            }
        },
        
        uploadLogo(sectionId, event) {
            const section = this.sections.find(s => s.instanceId === sectionId);
            if (section && section.type === 'header') {
                const file = event.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        section.data.logoUrl = e.target.result;
                    };
                    reader.readAsDataURL(file);
                }
            }
        },
        
        // Validate receipt data
        validateReceipt() {
            const errors = [];
            
            // Validate items section
            const itemsSections = this.sections.filter(s => s.type === 'items');
            itemsSections.forEach(section => {
                section.data.items.forEach((item, idx) => {
                    if (!item.name || item.name.trim() === '') {
                        errors.push(`Item ${idx + 1}: Name is required`);
                    }
                    if (isNaN(item.price) || item.price < 0) {
                        errors.push(`Item ${idx + 1}: Price must be a valid number`);
                    }
                    if (isNaN(item.quantity) || item.quantity < 1) {
                        errors.push(`Item ${idx + 1}: Quantity must be at least 1`);
                    }
                });
            });
            
            // Validate two-column sections
            const twoColSections = this.sections.filter(s => s.type === 'twoColumn');
            twoColSections.forEach(section => {
                section.data.customFields.forEach((field, idx) => {
                    if (field.label && !field.value) {
                        errors.push(`Two-column field "${field.label}": Value is required`);
                    }
                });
            });
            
            return errors;
        },
        
        // Actions - PDF DOWNLOAD with server-side watermarking
        async downloadReceipt() {
            console.log('📄 downloadReceipt() started');
            const receipt = document.getElementById('receipt-preview');
            if (!receipt) { 
                console.error('📄 Receipt preview element not found!');
                alert('Receipt preview not found'); 
                return; 
            }
            console.log('📄 Receipt preview found:', receipt);
            
            this.downloadingPdf = true;
            
            try {
                // Load libraries if needed
                console.log('📄 Loading libraries...');
                if (typeof html2canvas === 'undefined') {
                    console.log('📄 Loading html2canvas...');
                    await loadScript('https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js');
                }
                if (typeof window.jspdf === 'undefined') {
                    console.log('📄 Loading jsPDF...');
                    await loadScript('https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js');
                }
                console.log('📄 Libraries loaded successfully');
                
                const { jsPDF } = window.jspdf;
                
                // Wait for barcodes to render
                await new Promise(r => setTimeout(r, 300));
                
                // Capture the receipt WITHOUT the CSS watermark overlay
                // The server will add a Ghostscript watermark that's harder to remove
                // Include images with CORS support
                console.log('📄 Capturing receipt with html2canvas...');
                const canvas = await html2canvas(receipt, { 
                    scale: 2, 
                    useCORS: true,
                    backgroundColor: '#ffffff',
                    allowTaint: true,
                    logging: false,
                    ignoreElements: (el) => {
                        // Ignore watermark overlays (by id or class)
                        if (el.id === 'watermark-overlay') return true;
                        if (el.classList && el.classList.contains('watermark-overlay')) return true;
                        // Ignore elements with background-image in inline style or computed style
                        const inlineStyle = el.getAttribute && el.getAttribute('style');
                        if (inlineStyle && inlineStyle.includes('background-image')) return true;
                        if (el.style && el.style.backgroundImage && el.style.backgroundImage.includes('url(')) return true;
                        // Ignore z-20 elements (watermark overlays)
                        if (el.classList && el.classList.contains('z-20')) return true;
                        return false;
                    }
                });
                console.log('📄 Canvas captured:', canvas.width, 'x', canvas.height);
                
                // Convert to PDF
                const imgData = canvas.toDataURL('image/png');
                const receiptWidthPx = this.currentReceiptWidth || receipt.offsetWidth || 320;
                const pageWidthMm = 0.264583 * receiptWidthPx;
                const imgHeightMm = pageWidthMm * canvas.height / canvas.width;
                const footerHeightMm = 12;
                const pageHeightMm = imgHeightMm + footerHeightMm;
                
                const pdf = new jsPDF({ 
                    orientation: 'p', 
                    unit: 'mm', 
                    format: [pageWidthMm, pageHeightMm] 
                });
                pdf.addImage(imgData, 'PNG', 0, 0, pageWidthMm, imgHeightMm);
                
                // Add "fake receipt" footer
                pdf.setFontSize(7);
                pdf.setTextColor(180, 180, 180);
                pdf.text('fake receipt', 2, pageHeightMm - 2);
                
                // Get PDF as blob and send to server for Ghostscript watermarking
                // Use arraybuffer for better reliability
                const pdfArrayBuffer = pdf.output('arraybuffer');
                const pdfBlob = new Blob([pdfArrayBuffer], { type: 'application/pdf' });
                
                if (!pdfBlob || pdfBlob.size === 0) {
                    throw new Error('PDF generation failed - empty result');
                }
                
                // Get template info for logging
                const templateType = this.templateName || 'custom';
                const headerSection = this.sections.find(s => s.type === 'header');
                const storeName = headerSection?.data?.businessName || '';
                
                // Send to server for watermarking (Ghostscript embeds watermark in content stream)
                console.log('📄 Sending PDF to server for watermarking...');
                const formData = new FormData();
                formData.append('pdf', pdfBlob, 'receipt.pdf');
                formData.append('template_type', templateType);
                formData.append('store_name', storeName);
                
                const response = await fetch('/api/apply-watermark', {
                    method: 'POST',
                    body: formData
                });
                console.log('📄 Server response status:', response.status);
                
                if (!response.ok) {
                    const errorText = await response.text();
                    console.error('📄 Server error:', errorText);
                    throw new Error(`Server watermarking failed: ${response.status}`);
                }
                
                // Download the watermarked PDF from server
                console.log('📄 Getting watermarked PDF blob...');
                const watermarkedBlob = await response.blob();
                console.log('📄 Watermarked blob size:', watermarkedBlob.size);
                const url = URL.createObjectURL(watermarkedBlob);
                console.log('📄 Creating download link...');
                const a = document.createElement('a');
                a.href = url;
                a.download = 'receipt.pdf';
                document.body.appendChild(a);
                a.click();
                console.log('📄 Download triggered!');
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                
                // Show success
                this.downloadSuccessToast = true;
                setTimeout(() => this.downloadSuccessToast = false, 3000);
                
            } catch (e) {
                console.error('PDF error:', e);
                alert('Failed to download. Please try again.');
            } finally {
                this.downloadingPdf = false;
                this.downloadingFormat = null;
            }
        },
        
        // Download image at specified quality
        async downloadImage(quality) {
            // Quality levels: 'preview' (200px free), 'standard' (750px PRO), 'hd' (1500px PRO)
            const qualitySettings = {
                preview: { maxWidth: 200, scale: 1.5, requiresPro: false },
                standard: { maxWidth: 750, scale: 1.5, requiresPro: true },
                hd: { maxWidth: 1500, scale: 3, requiresPro: true }
            };
            
            const settings = qualitySettings[quality];
            if (!settings) {
                alert('Invalid quality setting');
                return;
            }
            
            // Check if PRO is required
            if (settings.requiresPro && !this.hasSubscription) {
                window.location.href = '/pricing';
                return;
            }
            
            const receipt = document.getElementById('receipt-preview');
            if (!receipt) { 
                alert('Receipt preview not found'); 
                return; 
            }
            
            this.downloadingFormat = quality;
            this.showDownloadMenu = false;
            
            try {
                // Load html2canvas if needed
                if (typeof html2canvas === 'undefined') {
                    await loadScript('https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js');
                }
                
                // Wait for barcodes to render
                await new Promise(r => setTimeout(r, 300));
                
                // Calculate scale based on target width
                const receiptWidth = receipt.offsetWidth || 320;
                const targetScale = settings.maxWidth / receiptWidth;
                const finalScale = Math.max(1, Math.min(targetScale, settings.scale));
                
                // Capture the receipt (include images with CORS support)
                const canvas = await html2canvas(receipt, { 
                    scale: finalScale, 
                    useCORS: true,
                    backgroundColor: '#ffffff',
                    allowTaint: true,
                    logging: false,
                    ignoreElements: (el) => {
                        // Ignore watermark overlays (by id or class)
                        if (el.id === 'watermark-overlay') return true;
                        if (el.classList && el.classList.contains('watermark-overlay')) return true;
                        // Ignore elements with background-image in inline style or computed style
                        const inlineStyle = el.getAttribute && el.getAttribute('style');
                        if (inlineStyle && inlineStyle.includes('background-image')) return true;
                        if (el.style && el.style.backgroundImage && el.style.backgroundImage.includes('url(')) return true;
                        // Ignore z-20 elements (watermark overlays)
                        if (el.classList && el.classList.contains('z-20')) return true;
                        return false;
                    }
                });
                
                // For free users (preview), add watermark to the image
                if (!this.hasSubscription) {
                    const ctx = canvas.getContext('2d');
                    ctx.save();
                    ctx.globalAlpha = 0.18;
                    
                    // Scale watermark based on canvas size for proper appearance at all resolutions
                    const scaleFactor = Math.max(canvas.width, canvas.height) / 500;
                    const fontSize = Math.max(10, Math.round(14 * scaleFactor));
                    const spacingY = Math.max(40, Math.round(60 * scaleFactor));
                    const spacingX = Math.max(80, Math.round(120 * scaleFactor));
                    
                    ctx.font = `bold ${fontSize}px Arial`;
                    ctx.fillStyle = '#555555';
                    ctx.translate(canvas.width / 2, canvas.height / 2);
                    ctx.rotate(-30 * Math.PI / 180);
                    
                    // Draw multiple watermarks with scaled spacing
                    for (let y = -canvas.height * 1.5; y < canvas.height * 1.5; y += spacingY) {
                        for (let x = -canvas.width * 1.5; x < canvas.width * 1.5; x += spacingX) {
                            ctx.fillText('RECEIPTMAKE', x, y);
                        }
                    }
                    ctx.restore();
                }
                
                // Convert to blob and download
                // Use toDataURL as fallback if toBlob fails (CORS tainted canvas)
                try {
                    const dataUrl = canvas.toDataURL('image/png');
                    const a = document.createElement('a');
                    a.href = dataUrl;
                    a.download = `receipt-${quality}.png`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    
                    // Show success
                    this.downloadSuccessToast = true;
                    setTimeout(() => this.downloadSuccessToast = false, 3000);
                } catch (blobError) {
                    console.error('Canvas export error:', blobError);
                    throw new Error('Could not export image. Try removing external logos.');
                }
                
            } catch (e) {
                console.error('Image download error:', e);
                alert('Failed to download. Please try again.');
            } finally {
                this.downloadingFormat = null;
            }
        },
        
        // Download PDF (PRO only)
        async downloadPDF() {
            console.log('📄 downloadPDF called, hasSubscription:', this.hasSubscription);
            if (!this.hasSubscription) {
                console.log('📄 No subscription, redirecting to pricing');
                window.location.href = '/pricing';
                return;
            }
            try {
                console.log('📄 Starting PDF download...');
                await this.downloadReceipt();
                console.log('📄 PDF download completed successfully');
            } catch (error) {
                console.error('📄 PDF download error:', error);
            }
        },
        
        resetForm() {
            const confirmed = confirm('⚠️ Are you sure?\n\nThis will permanently delete all your work.\n\nThis cannot be undone.');
            if (!confirmed) {
                return;
            }
            
            // Clear auto-save and reload
            this.clearAutoSave();
            location.reload();
        },
        
        // Auto-save functionality
        startAutoSave() {
            // Auto-save every 10 seconds as fallback redundancy
            this.autoSaveTimer = setInterval(() => {
                this.autoSave();
            }, 10000); // 10 seconds
        },
        
        // Debounced auto-save triggered on every change (500ms delay)
        triggerDebouncedAutoSave() {
            // Clear any existing debounce timer
            if (this.autoSaveDebounceTimer) {
                clearTimeout(this.autoSaveDebounceTimer);
            }
            
            // Set new debounce timer (500ms delay after last change)
            this.autoSaveDebounceTimer = setTimeout(() => {
                this.autoSave();
            }, 500);
        },
        
        autoSave() {
            try {
                // Don't auto-save if there are no sections (empty state)
                if (this.sections.length === 0) {
                    return;
                }
                
                // Extract template slug from URL for comparison on restore
                const templateSlug = this.getTemplateSlugFromUrl();
                
                // Save current receipt configuration to localStorage with template-specific key
                const autoSaveData = {
                    sections: JSON.parse(JSON.stringify(this.sections)),
                    nextInstanceId: this.nextInstanceId,
                    timestamp: new Date().toISOString(),
                    savedAt: new Date().toLocaleTimeString(),
                    templateName: this.templateName || '',
                    templateSlug: templateSlug, // Store slug for comparison on restore
                    url: window.location.pathname
                };
                
                // Use template-specific key to prevent cross-template conflicts
                localStorage.setItem(this.autoSaveKey, JSON.stringify(autoSaveData));
                this.lastAutoSave = autoSaveData.savedAt;
                
                // Log to verify save is working
                console.log('✓ Receipt auto-saved at', this.lastAutoSave, 'with', this.sections.length, 'sections');
                
            } catch (error) {
                console.error('❌ Auto-save error:', error);
                // Silently fail - don't interrupt user
            }
        },
        
        clearAutoSave() {
            // Clear template-specific auto-save key
            localStorage.removeItem(this.autoSaveKey);
            if (this.autoSaveTimer) {
                clearInterval(this.autoSaveTimer);
                this.autoSaveTimer = null;
            }
            if (this.autoSaveDebounceTimer) {
                clearTimeout(this.autoSaveDebounceTimer);
                this.autoSaveDebounceTimer = null;
            }
        },
        
        handleSaveTemplate() {
            const errors = this.validateReceipt();
            if (errors.length > 0) {
                alert('Please fix validation errors before saving template');
                return;
            }
            
            // Check authentication status
            if (!this.isAuthenticated) {
                // CRITICAL: Store template BEFORE showing login modal to prevent data loss
                this.storeTemplateForSave();
                
                // Dispatch event to open login modal (modal is at root level)
                const headerSection = this.sections.find(s => s.type === 'header');
                const dateTimeSection = this.sections.find(s => s.type === 'dateTime');
                const itemsSection = this.sections.find(s => s.type === 'items');
                
                window.dispatchEvent(new CustomEvent('open-login-modal', {
                    detail: {
                        businessName: headerSection?.data.businessName || 'Your Business',
                        dateTime: dateTimeSection?.data.dateTime || new Date().toLocaleString(),
                        items: itemsSection?.data.items || [],
                        total: this.calculateSubtotal()
                    }
                }));
            } else {
                // Show save template modal for authenticated users
                this.showSaveTemplateModal = true;
            }
        },
        
        async handleRemoveWatermark() {
            // Allow users to remove watermark even with validation errors
            // This is a paid conversion action and shouldn't be blocked
            
            // Store template for auto-save with watermark removal intent
            // This data will persist through the pricing → checkout → account creation flow
            const config = {
                sections: this.sections.map(section => ({
                    type: section.type,
                    data: section.data,
                    collapsed: section.collapsed
                }))
            };
            
            // Generate a descriptive name from the receipt
            const headerSection = this.sections.find(s => s.type === 'header');
            let businessName = headerSection?.data.businessName || 'Business';
            
            // If business name is still "Business" and we have a template name, use that instead
            if (businessName === 'Business' && this.templateName) {
                businessName = this.templateName;
            }
            
            // Convert to title case: "WALMART" -> "Walmart"
            const defaultName = businessName.toLowerCase().replace(/\b\w/g, char => char.toUpperCase());
            
            const pendingSave = {
                intent: 'remove_watermark',
                name: defaultName,
                description: 'Auto-saved before removing watermark',
                config: config
            };
            
            try {
                // BACKUP: Save to localStorage so users can restore if they come back
                const templateSlug = this.getTemplateSlugFromUrl();
                localStorage.setItem('savedReceipt', JSON.stringify({
                    config: config,
                    timestamp: new Date().toISOString(),
                    name: defaultName,
                    templateSlug: templateSlug
                }));
                
                // Store receipt server-side (secure) - timestamp added by server
                const response = await fetch('/api/store-pending-receipt', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(pendingSave)
                });
                
                if (!response.ok) {
                    throw new Error('Failed to store receipt');
                }
                
                // Redirect to pricing page
                // User will see plans → choose one → go through Stripe checkout + account creation
                // After payment completes, the receipt will auto-save as a template
                window.location.href = '/pricing';
                
            } catch (error) {
                console.error('Error storing pending receipt:', error);
                alert('Failed to store receipt. Please try again.');
            }
        },
        
        storeTemplateForSave() {
            // Check if there's already a pending save with 'remove_watermark' intent
            // If so, don't overwrite it - the remove watermark flow takes precedence
            const existingPendingSave = sessionStorage.getItem('pending_template_save');
            if (existingPendingSave) {
                try {
                    const existing = JSON.parse(existingPendingSave);
                    if (existing.intent === 'remove_watermark') {
                        // Don't overwrite - the remove watermark flow is already set up
                        return;
                    }
                } catch (e) {
                    // If parsing fails, continue with normal flow
                }
            }
            
            // Store current template configuration in sessionStorage
            const config = {
                sections: this.sections.map(section => ({
                    type: section.type,
                    data: section.data,
                    collapsed: section.collapsed
                }))
            };
            
            // Use simple default name "Template 1" for auto-save
            const defaultName = 'Template 1';
            
            const pendingSave = {
                intent: 'save_template',
                name: defaultName,
                description: '',
                config: config,
                timestamp: Date.now(),
                nextUrl: window.location.pathname,
                autoSave: true // Flag to auto-save after login
            };
            
            sessionStorage.setItem('pending_template_save', JSON.stringify(pendingSave));
        },
        
        checkPendingTemplateSave() {
            if (!this.isAuthenticated) {
                return;
            }
            
            const pendingSaveData = sessionStorage.getItem('pending_template_save');
            if (!pendingSaveData) {
                return;
            }
            
            try {
                const pendingSave = JSON.parse(pendingSaveData);
                
                // Support both 'save_template' and 'remove_watermark' intents
                if (!['save_template', 'remove_watermark'].includes(pendingSave.intent)) {
                    sessionStorage.removeItem('pending_template_save');
                    return;
                }
                
                const age = Date.now() - (pendingSave.timestamp || 0);
                if (age > 10 * 60 * 1000) {
                    sessionStorage.removeItem('pending_template_save');
                    return;
                }
                
                if (!pendingSave.config || !pendingSave.config.sections || !pendingSave.name) {
                    sessionStorage.removeItem('pending_template_save');
                    return;
                }
                
                this.loadTemplate(pendingSave.config);
                this.hasPendingSave = true;
                
                this.$nextTick(() => {
                    // Check if this is an auto-save (user just created account from login modal)
                    if (pendingSave.autoSave) {
                        // Auto-save the template immediately
                        this.autoSaveTemplateAndRedirect(
                            pendingSave.name, 
                            pendingSave.description || '',
                            pendingSave.intent === 'remove_watermark' ? '/pricing' : null
                        );
                    } else {
                        // Manual save flow - show modal
                        this.saveTemplateName = pendingSave.name;
                        this.saveTemplateDescription = pendingSave.description || '';
                        this.showSaveTemplateModal = true;
                    }
                    
                    this.initSortable();
                    
                    sessionStorage.removeItem('pending_template_save');
                });
                
            } catch (error) {
                console.error('Error processing pending template save:', error);
                sessionStorage.removeItem('pending_template_save');
            }
        },
        
        checkForSavedReceipt() {
            // Skip auto-restore if user is loading a saved template from dashboard
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.has('load_template')) {
                return;
            }
            
            // Get the current template slug to verify saved receipt matches
            const currentTemplateSlug = this.getTemplateSlugFromUrl();
            
            // Check for template-specific auto-save (most recent)
            // Each template has its own unique key based on URL path, so no cross-template conflicts
            const autoSaveData = localStorage.getItem(this.autoSaveKey);
            if (autoSaveData) {
                try {
                    const autoSave = JSON.parse(autoSaveData);
                    
                    // Check if auto-save is less than 7 days old
                    const savedTime = new Date(autoSave.timestamp);
                    const now = new Date();
                    const daysDiff = (now - savedTime) / (1000 * 60 * 60 * 24);
                    
                    if (daysDiff > 7) {
                        // Expired, remove it
                        localStorage.removeItem(this.autoSaveKey);
                        return;
                    }
                    
                    // Store the saved template slug for comparison
                    this.savedTemplateSlug = autoSave.templateSlug || '';
                    
                    // CRITICAL: Only show restore modal if saved template matches current template
                    // This prevents Store Express receipts from appearing on Walmart template, etc.
                    const savedSlug = autoSave.templateSlug || '';
                    if (savedSlug !== currentTemplateSlug) {
                        console.log(`Auto-save template "${savedSlug}" doesn't match current template "${currentTemplateSlug}" - skipping restore`);
                        return;
                    }
                    
                    // Store config for modal - don't restore yet, let user choose
                    this.pendingRestoreConfig = { 
                        sections: autoSave.sections, 
                        nextInstanceId: autoSave.nextInstanceId,
                        savedAt: autoSave.savedAt || 'earlier'
                    };
                    this.showRestoreModal = true;
                    console.log('Found saved receipt for matching template - showing restore modal');
                    return;
                } catch (error) {
                    console.error('Error loading auto-save:', error);
                    localStorage.removeItem(this.autoSaveKey);
                }
            }
            
            // Check for manual saved receipt (from "Remove Watermark" flow)
            const savedData = localStorage.getItem('savedReceipt');
            if (!savedData) {
                return;
            }
            
            try {
                const saved = JSON.parse(savedData);
                
                // Check if saved receipt is less than 7 days old
                const savedTime = new Date(saved.timestamp);
                const now = new Date();
                const daysDiff = (now - savedTime) / (1000 * 60 * 60 * 24);
                
                if (daysDiff > 7) {
                    // Expired, remove it
                    localStorage.removeItem('savedReceipt');
                    return;
                }
                
                // CRITICAL: Check if the saved receipt's template matches current template
                // This prevents Store Express from showing on Kroger, etc.
                const savedReceiptSlug = saved.templateSlug || '';
                if (savedReceiptSlug !== currentTemplateSlug) {
                    console.log(`Saved receipt template "${savedReceiptSlug}" doesn't match current template "${currentTemplateSlug}" - skipping restore`);
                    return;
                }
                
                // Store config for modal - don't restore yet, let user choose
                if (saved.config) {
                    this.pendingRestoreConfig = { 
                        sections: saved.config.sections, 
                        nextInstanceId: saved.config.nextInstanceId || 1,
                        savedAt: 'earlier'
                    };
                    this.showRestoreModal = true;
                    console.log('Found saved receipt for matching template - showing restore modal');
                }
                
            } catch (error) {
                console.error('Error restoring saved receipt:', error);
                localStorage.removeItem('savedReceipt');
            }
        },
        
        // User chose to continue with saved receipt (already loaded, just dismiss banner)
        handleRestoreContinue() {
            console.log('User chose to continue with saved receipt');
            this.showRestoreModal = false;
            this.pendingRestoreConfig = null;
        },
        
        // User chose to start fresh
        handleRestoreStartFresh() {
            // Clear the saved data
            this.clearAutoSave();
            localStorage.removeItem('savedReceipt');
            
            // Load fresh template or defaults
            if (this.templateConfig) {
                this.loadTemplate(this.templateConfig);
                console.log('User chose to start fresh - loading template');
            } else {
                // Create default sections for base generator
                this.createDefaultSections();
                console.log('User chose to start fresh - using defaults');
            }
            
            this.showRestoreModal = false;
            this.pendingRestoreConfig = null;
            
            // Sync debounced sections
            this.$nextTick(() => {
                this.debouncedSections = JSON.parse(JSON.stringify(this.sections));
            });
        },
        
        // Create default sections for fresh start
        createDefaultSections() {
            const settingsSection = this.createSection('settings', true);
            settingsSection.data.selectedFont = 'font-1';
            settingsSection.data.textColor = '#000000';
            settingsSection.data.currencyFormat = '$X';
            
            const headerSection = this.createSection('header', true);
            headerSection.data.logoUrl = 'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80" viewBox="0 0 80 80"><circle cx="40" cy="40" r="35" fill="#000000" stroke="#333333" stroke-width="2"/><text x="40" y="50" font-family="Arial" font-size="32" font-weight="bold" fill="#ffffff" text-anchor="middle">SE</text></svg>');
            headerSection.data.logoSize = 35;
            headerSection.data.businessName = 'STORE EXPRESS';
            headerSection.data.line1 = '123 Main Street';
            headerSection.data.line2 = 'Springfield, IL 62701';
            headerSection.data.line3 = '(555) 123-4567';
            headerSection.data.headerAlignment = 'center';
            
            const dateTimeSection = this.createSection('dateTime', true);
            dateTimeSection.data.dateTime = new Date().toLocaleString('en-US', {
                month: '2-digit',
                day: '2-digit', 
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: true
            });
            dateTimeSection.data.dateAlignment = 'center';
            
            const itemsSection = this.createSection('items', false);
            itemsSection.data.items = [
                { id: 'item_1', quantity: 2, name: 'Wireless Mouse', price: 24.99 },
                { id: 'item_2', quantity: 1, name: 'USB-C Cable (6ft)', price: 12.99 },
                { id: 'item_3', quantity: 1, name: 'Phone Screen Protector', price: 9.99 },
                { id: 'item_4', quantity: 3, name: 'AA Batteries (4-pack)', price: 8.99 }
            ];
            
            const paymentSection = this.createSection('payment', true);
            paymentSection.data.taxRate = 8.5;
            paymentSection.data.showTaxRate = true;
            paymentSection.data.paymentType = 'card';
            paymentSection.data.paymentFields = [
                { label: 'Card number', value: '**** **** **** 4922' },
                { label: 'Card type', value: 'Debit' },
                { label: 'Card entry', value: 'Chip' },
                { label: 'Transaction #', value: '458721' },
                { label: 'Cashier', value: 'Sarah M.' },
                { label: 'Register', value: '03' },
                { label: 'REWARDS MEMBER', value: '#SE892341' },
                { label: 'Points earned', value: '45' },
                { label: 'Total points', value: '1,245' }
            ];
            
            const messageSection = this.createSection('customMessage', true);
            messageSection.data.customMessage = 'Thank you for shopping with us!\n\nReturns accepted within 30 days with receipt.\nFor assistance, call us at (555) 123-4567';
            messageSection.data.messageAlignment = 'center';
            
            const promoSection = this.createSection('customMessage', true);
            promoSection.data.customMessage = 'Visit us online at StoreExpress.com for exclusive deals!\n\nSign up for our rewards program and earn 1 point per dollar spent. New members get 500 bonus points!\n\nJoin our email list for 10% off your next purchase.\n\nFollow us @StoreExpress on social media for daily deals, giveaways, and special promotions.\n\nShop with confidence - 100% satisfaction guaranteed or your money back.';
            promoSection.data.messageAlignment = 'center';
            
            const barcodeSection = this.createSection('barcode', true);
            barcodeSection.data.barcodeValue = '458721';
            
            this.sections = [
                settingsSection,
                headerSection,
                dateTimeSection,
                itemsSection,
                paymentSection,
                messageSection,
                promoSection,
                barcodeSection
            ];
        },
        
        
        async saveTemplate() {
            this.saveTemplateError = '';
            this.saveTemplateSuccess = false;
            this.saveTemplateLoading = true;
            
            if (!this.saveTemplateName.trim()) {
                this.saveTemplateError = 'Template name is required';
                this.saveTemplateLoading = false;
                return;
            }
            
            const errors = this.validateReceipt();
            if (errors.length > 0) {
                this.saveTemplateError = 'Please fix validation errors before saving';
                this.saveTemplateLoading = false;
                return;
            }
            
            const config = {
                sections: this.sections.map(section => ({
                    type: section.type,
                    data: section.data,
                    collapsed: section.collapsed
                }))
            };
            
            if (!this.isAuthenticated) {
                const pendingSave = {
                    intent: 'save_template',
                    name: this.saveTemplateName.trim(),
                    description: this.saveTemplateDescription.trim(),
                    config: config,
                    timestamp: Date.now(),
                    nextUrl: window.location.pathname,
                    autoSave: true
                };
                
                sessionStorage.setItem('pending_template_save', JSON.stringify(pendingSave));
                
                // Close modal and show login modal with receipt preview
                this.showSaveTemplateModal = false;
                
                const headerSection = this.sections.find(s => s.type === 'header');
                const dateTimeSection = this.sections.find(s => s.type === 'dateTime');
                const itemsSection = this.sections.find(s => s.type === 'items');
                
                window.dispatchEvent(new CustomEvent('open-login-modal', {
                    detail: {
                        businessName: headerSection?.data.businessName || 'Your Business',
                        dateTime: dateTimeSection?.data.dateTime || new Date().toLocaleString(),
                        items: itemsSection?.data.items || [],
                        total: this.calculateSubtotal()
                    }
                }));
                return;
            }
            
            try {
                const response = await fetch('/api/templates', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name: this.saveTemplateName.trim(),
                        description: this.saveTemplateDescription.trim(),
                        template_type: 'custom',
                        config_json: config
                    })
                });
                
                const data = await response.json();
                
                if (!data.success) {
                    throw new Error(data.error || 'Failed to save template');
                }
                
                this.saveTemplateSuccess = true;
                this.saveTemplateLoading = false;
                
                setTimeout(() => {
                    this.showSaveTemplateModal = false;
                    this.saveTemplateName = '';
                    this.saveTemplateDescription = '';
                    this.saveTemplateSuccess = false;
                    // Redirect to dashboard
                    window.location.href = '/dashboard';
                }, 1500);
                
            } catch (error) {
                console.error('Error saving template:', error);
                this.saveTemplateError = error.message || 'Failed to save template. Please try again.';
                this.saveTemplateLoading = false;
            }
        },
        
        // Auto-save template after login (no modal)
        async autoSaveTemplate(name, description, redirectToDashboard = false) {
            const config = {
                sections: this.sections.map(section => ({
                    type: section.type,
                    data: section.data,
                    collapsed: section.collapsed
                }))
            };
            
            try {
                const response = await fetch('/api/templates', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name: name.trim(),
                        description: description.trim(),
                        template_type: 'custom',
                        config_json: config
                    })
                });
                
                const data = await response.json();
                
                if (!data.success) {
                    throw new Error(data.error || 'Failed to save template');
                }
                
                // Show success notification
                this.showAutoSaveSuccess = true;
                
                if (redirectToDashboard) {
                    // Redirect to dashboard after showing success
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 1500);
                } else {
                    // Hide notification after 5 seconds
                    setTimeout(() => {
                        this.showAutoSaveSuccess = false;
                    }, 5000);
                }
                
            } catch (error) {
                console.error('Error auto-saving template:', error);
                // Still show a notification but with error message
                alert('Template loaded but failed to save automatically. Please save manually from the Save button.');
            }
        },
        
        // Auto-save template and redirect to a URL (for watermark removal flow)
        async autoSaveTemplateAndRedirect(name, description, redirectUrl) {
            const config = {
                sections: this.sections.map(section => ({
                    type: section.type,
                    data: section.data,
                    collapsed: section.collapsed
                }))
            };
            
            try {
                const response = await fetch('/api/templates', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name: name.trim(),
                        description: description.trim(),
                        template_type: 'custom',
                        config_json: config
                    })
                });
                
                const data = await response.json();
                
                if (!data.success) {
                    throw new Error(data.error || 'Failed to save template');
                }
                
                // Show success notification
                this.showAutoSaveSuccess = true;
                
                // If redirect URL is provided, redirect after showing success
                if (redirectUrl) {
                    setTimeout(() => {
                        window.location.href = redirectUrl;
                    }, 1500);
                } else {
                    // Hide notification after 5 seconds
                    setTimeout(() => {
                        this.showAutoSaveSuccess = false;
                    }, 5000);
                }
                
            } catch (error) {
                console.error('Error auto-saving template:', error);
                // If redirect is needed, still redirect even if save failed
                if (redirectUrl) {
                    alert('Template loaded but failed to save automatically. You can save it later from your dashboard.');
                    setTimeout(() => {
                        window.location.href = redirectUrl;
                    }, 2000);
                } else {
                    alert('Template loaded but failed to save automatically. Please save manually from the Save button.');
                }
            }
        }
    }
}

// Export to global scope for Alpine.js
window.advancedReceiptGeneratorV2 = advancedReceiptGeneratorV2;
console.log('Advanced receipt generator loaded and exported to window');
