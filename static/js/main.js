/*
Main JavaScript file for Jambo Management Cloud System
Common functions aur utilities
*/

// Global configuration
const CONFIG = {
    API_BASE: '/api',
    SEARCH_DELAY: 500,
    METER_TO_YARD_RATIO: 1.08325,
    DEFAULT_JAMBO_WIDTH: 1280
};

// Utility Functions
const Utils = {
    // Format currency
    formatCurrency: function(amount) {
        return '₨' + new Intl.NumberFormat('en-PK').format(amount);
    },
    
    // Format numbers with commas
    formatNumber: function(number) {
        return new Intl.NumberFormat('en-US').format(number);
    },
    
    // Convert meters to yards
    metersToYards: function(meters) {
        return Math.round(meters * CONFIG.METER_TO_YARD_RATIO);
    },
    
    // Extract width from size string
    extractWidth: function(sizeString) {
        try {
            return parseInt(sizeString.split('mm')[0]);
        } catch (e) {
            return 0;
        }
    },
    
    // Extract pieces from quantity string
    extractPieces: function(qtyString) {
        try {
            return parseInt(qtyString.replace(/\D/g, ''));
        } catch (e) {
            return 0;
        }
    },
    
    // Calculate shaft cutting
    calculateShaftCutting: function(width, jamboWidth = CONFIG.DEFAULT_JAMBO_WIDTH) {
        const piecesPerShaft = Math.floor(jamboWidth / width);
        const usedWidth = piecesPerShaft * width;
        const wastage = jamboWidth - usedWidth;
        const efficiency = (usedWidth / jamboWidth) * 100;
        
        return {
            piecesPerShaft: piecesPerShaft,
            usedWidth: usedWidth,
            wastage: wastage,
            efficiency: Math.round(efficiency * 10) / 10
        };
    },
    
    // Show loading state
    showLoading: function(element, text = 'Loading...') {
        const loadingHtml = `<i class="loading-spinner me-2"></i>${text}`;
        if (element.is('button')) {
            element.data('original-html', element.html());
            element.html(loadingHtml).prop('disabled', true);
        } else {
            element.html(loadingHtml);
        }
    },
    
    // Hide loading state
    hideLoading: function(element) {
        if (element.is('button')) {
            element.html(element.data('original-html')).prop('disabled', false);
        }
    },
    
    // Show toast notification
    showToast: function(message, type = 'info') {
        const toastId = 'toast-' + Date.now();
        const toastClass = type === 'success' ? 'bg-success' : 
                          type === 'error' ? 'bg-danger' : 
                          type === 'warning' ? 'bg-warning' : 'bg-info';
        
        const toastHtml = `
            <div class="toast ${toastClass} text-white" id="${toastId}" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;
        
        // Create toast container if it doesn't exist
        if (!$('#toast-container').length) {
            $('body').append('<div id="toast-container" class="toast-container position-fixed top-0 end-0 p-3"></div>');
        }
        
        $('#toast-container').append(toastHtml);
        const toast = new bootstrap.Toast(document.getElementById(toastId));
        toast.show();
        
        // Remove toast element after it's hidden
        document.getElementById(toastId).addEventListener('hidden.bs.toast', function() {
            this.remove();
        });
    },
    
    // Confirm dialog
    confirmAction: function(message, callback) {
        if (confirm(message)) {
            callback();
        }
    },
    
    // Debounce function
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// Search functionality
const Search = {
    init: function() {
        // Real-time search for all search inputs
        $('.real-time-search').each(function() {
            const input = $(this);
            const form = input.closest('form');
            
            input.on('input', Utils.debounce(function() {
                const searchTerm = input.val();
                if (searchTerm.length >= 2 || searchTerm.length === 0) {
                    form.submit();
                }
            }, CONFIG.SEARCH_DELAY));
        });
    },
    
    // API search for dropdowns
    apiSearch: function(endpoint, searchTerm, callback) {
        $.ajax({
            url: CONFIG.API_BASE + endpoint,
            method: 'GET',
            data: { q: searchTerm },
            success: callback,
            error: function(xhr, status, error) {
                console.error('Search API error:', error);
                Utils.showToast('Search failed. Please try again.', 'error');
            }
        });
    }
};

// Production calculations
const Production = {
    // Calculate production requirements
    calculate: function(itemData, jamboData) {
        const width = Utils.extractWidth(itemData.size);
        const pieces = Utils.extractPieces(itemData.qty);
        const length = parseInt(itemData.size.split('x')[1].split(' ')[0]);
        
        const shaftInfo = Utils.calculateShaftCutting(width);
        const shaftsNeeded = Math.ceil(pieces / shaftInfo.piecesPerShaft);
        const yardsNeeded = shaftsNeeded * length;
        
        return {
            width: width,
            length: length,
            pieces: pieces,
            piecesPerShaft: shaftInfo.piecesPerShaft,
            shaftsNeeded: shaftsNeeded,
            yardsNeeded: yardsNeeded,
            efficiency: shaftInfo.efficiency,
            feasible: yardsNeeded <= jamboData.balance_yard,
            remainingYards: jamboData.balance_yard - yardsNeeded
        };
    },
    
    // API calculation call
    apiCalculate: function(itemId, jamboId, callback) {
        $.ajax({
            url: CONFIG.API_BASE + '/production/calculate',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                item_id: itemId,
                jambo_id: jamboId
            }),
            success: callback,
            error: function(xhr, status, error) {
                console.error('Production calculation error:', error);
                Utils.showToast('Calculation failed. Please try again.', 'error');
            }
        });
    }
};

// Form enhancements
const Forms = {
    init: function() {
        // Add asterisk to required fields
        $('input[required], select[required], textarea[required]').each(function() {
            const label = $('label[for="' + $(this).attr('id') + '"]');
            if (label.length && !label.find('.text-danger').length) {
                label.append(' <span class="text-danger">*</span>');
            }
        });
        
        // Real-time validation
        $('.form-control').on('blur', function() {
            Forms.validateField($(this));
        });
        
        // Number input formatting
        $('.format-number').on('blur', function() {
            const value = parseFloat($(this).val());
            if (!isNaN(value)) {
                $(this).val(Utils.formatNumber(value));
            }
        });
    },
    
    validateField: function(field) {
        let isValid = true;
        const value = field.val().trim();
        
        // Required field validation
        if (field.prop('required') && !value) {
            isValid = false;
            field.addClass('is-invalid');
            Forms.showFieldError(field, 'This field is required');
        } else {
            field.removeClass('is-invalid');
            Forms.hideFieldError(field);
        }
        
        // Type-specific validation
        if (value && field.attr('type') === 'email') {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(value)) {
                isValid = false;
                field.addClass('is-invalid');
                Forms.showFieldError(field, 'Please enter a valid email address');
            }
        }
        
        if (value && field.attr('type') === 'number') {
            const numValue = parseFloat(value);
            const min = field.attr('min');
            const max = field.attr('max');
            
            if (isNaN(numValue)) {
                isValid = false;
                field.addClass('is-invalid');
                Forms.showFieldError(field, 'Please enter a valid number');
            } else if (min && numValue < parseFloat(min)) {
                isValid = false;
                field.addClass('is-invalid');
                Forms.showFieldError(field, `Value must be at least ${min}`);
            } else if (max && numValue > parseFloat(max)) {
                isValid = false;
                field.addClass('is-invalid');
                Forms.showFieldError(field, `Value must be at most ${max}`);
            }
        }
        
        return isValid;
    },
    
    showFieldError: function(field, message) {
        let errorDiv = field.next('.invalid-feedback');
        if (!errorDiv.length) {
            errorDiv = $('<div class="invalid-feedback"></div>');
            field.after(errorDiv);
        }
        errorDiv.text(message);
    },
    
    hideFieldError: function(field) {
        field.next('.invalid-feedback').remove();
    },
    
    validateForm: function(form) {
        let isValid = true;
        form.find('.form-control').each(function() {
            if (!Forms.validateField($(this))) {
                isValid = false;
            }
        });
        return isValid;
    }
};

// Table enhancements
const Tables = {
    init: function() {
        // Add hover effects
        $('.table tbody tr').hover(
            function() {
                $(this).addClass('table-active');
            },
            function() {
                $(this).removeClass('table-active');
            }
        );
        
        // Sortable columns (if needed)
        $('.sortable-table th[data-sort]').click(function() {
            const column = $(this).data('sort');
            Tables.sortTable($(this).closest('table'), column);
        });
    },
    
    sortTable: function(table, column) {
        // Simple table sorting implementation
        console.log('Sorting by:', column);
        // Implementation would go here
    }
};

// Initialize everything when document is ready
$(document).ready(function() {
    // Initialize all modules
    Search.init();
    Forms.init();
    Tables.init();
    
    // Global click handlers
    $(document).on('click', '.confirm-action', function(e) {
        e.preventDefault();
        const message = $(this).data('confirm') || 'Are you sure?';
        const href = $(this).attr('href');
        
        Utils.confirmAction(message, function() {
            window.location.href = href;
        });
    });
    
    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        $('.alert').fadeOut();
    }, 5000);
    
    // Add loading states to form submissions
    $('form').on('submit', function() {
        const submitBtn = $(this).find('button[type="submit"]');
        if (submitBtn.length) {
            Utils.showLoading(submitBtn, 'Processing...');
        }
    });
    
    // Modal close pe fields reset karo
    $('#editItemModal').on('hidden.bs.modal', function () {
        document.getElementById('editItemId').value = '';
        document.getElementById('editSizeMM').value = '';
        document.getElementById('editSizeYard').value = '';
        document.getElementById('editColor').value = '';
        document.getElementById('editBrand').value = '';
        document.getElementById('editMicron').value = '';
        document.getElementById('editPacking').value = '';
    });
    
    console.log('🌐 Jambo Management Cloud System initialized!');
});

// Export for use in other scripts
window.JamboApp = {
    Utils: Utils,
    Search: Search,
    Production: Production,
    Forms: Forms,
    Tables: Tables
}; 

// Edit Item Function
function editItem(itemId) {
    fetch(`/stock/api/items/${itemId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const item = data.item;
                console.log('Edit item:', item); // Debug
                document.getElementById('editItemId').value = item.id;
                document.getElementById('editSizeMM').value = item.size_mm;
                document.getElementById('editSizeYard').value = item.size_yard;
                document.getElementById('editColor').value = item.color;
                document.getElementById('editBrand').value = item.brand;
                document.getElementById('editMicron').value = item.micron;
                document.getElementById('editPacking').value = item.packing ? item.packing : '';
                setTimeout(() => {
                    document.getElementById('editPacking').value = item.packing ? item.packing : '';
                }, 100);
                var modal = new bootstrap.Modal(document.getElementById('editItemModal'));
                modal.show();
            } else {
                Utils.showToast('Item not found!', 'error');
            }
        });
}

function saveEditItem() {
    const itemId = document.getElementById('editItemId').value;
    const data = {
        size_mm: document.getElementById('editSizeMM').value,
        size_yard: document.getElementById('editSizeYard').value,
        color: document.getElementById('editColor').value,
        brand: document.getElementById('editBrand').value,
        micron: document.getElementById('editMicron').value,
        packing: document.getElementById('editPacking').value || 72
    };
    fetch(`/stock/api/update/${itemId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Utils.showToast('Item updated!', 'success');
            $('#editItemModal').modal('hide');
            loadStockItems();
        } else {
            Utils.showToast(data.message || 'Update failed!', 'error');
        }
    });
} 

function loadStockItems() {
    fetch('/stock/api/items')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const tbody = document.getElementById('stockTableBody');
                tbody.innerHTML = '';
                data.items.forEach(item => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${item.id}</td>
                        <td>${item.size_mm}mm x ${item.size_yard} Yard</td>
                        <td>${item.color}</td>
                        <td>${item.brand}</td>
                        <td>${item.micron}mic</td>
                        <td>${item.packing}</td>
                        <td>${item.created_date ? item.created_date.split('T')[0] : ''}</td>
                        <td><span class="status-badge status-${item.is_active ? 'active' : 'inactive'}">${item.is_active ? 'Active' : 'Inactive'}</span></td>
                        <td>
                            <button class="btn btn-sm btn-warning me-1" onclick="editItem(${item.id})"><i class="fas fa-edit"></i></button>
                            <button class="btn btn-sm btn-danger" onclick="deleteItem(${item.id})"><i class="fas fa-trash"></i></button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        });
} 