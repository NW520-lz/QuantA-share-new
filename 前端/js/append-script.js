
setTimeout(() => {
    // Sync ranges and numbers
    const panels = document.querySelectorAll('.mode-panel');
    panels.forEach(panel => {
        const rows = panel.querySelectorAll('.grid.grid-cols-12');
        rows.forEach((row, rowIndex) => {
            const rangeInput = row.querySelector('input[type="range"]');
            const numInput = row.querySelector('input[type="number"]');
            
            if (rangeInput && numInput) {
                // Assign deterministic IDs if missing
                if (!rangeInput.id) rangeInput.id = `range-${panel.className.includes('swing') ? 'swing' : 'short'}-${rowIndex}`;
                if (!numInput.id) numInput.id = `num-${panel.className.includes('swing') ? 'swing' : 'short'}-${rowIndex}`;

                rangeInput.addEventListener('input', () => numInput.value = rangeInput.value);
                numInput.addEventListener('input', () => rangeInput.value = numInput.value);
            }
        });
    });

    // Checkboxes 
    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach((cb, i) => {
        if (!cb.id) cb.id = `filter-cb-${i}`;
    });

    // Load from localStorage
    const saved = localStorage.getItem('quantA_strategy_params');
    if (saved) {
        try {
            const data = JSON.parse(saved);
            Object.keys(data).forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    if (el.type === 'checkbox') {
                        el.checked = data[id];
                    } else {
                        el.value = data[id];
                    }
                }
            });
        } catch(e) {}
    }

    // Bind Save Button
    const saveBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('保存并下发'));
    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            saveBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">sync</span> 保存中...';
            
            const dataToSave = {};
            document.querySelectorAll('input[type="range"], input[type="number"]').forEach(input => {
                if (input.id) dataToSave[input.id] = input.value;
            });
            document.querySelectorAll('input[type="checkbox"]').forEach(input => {
                if (input.id) dataToSave[input.id] = input.checked;
            });

            localStorage.setItem('quantA_strategy_params', JSON.stringify(dataToSave));

            setTimeout(() => {
                saveBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">check</span> 已下发引擎';
                saveBtn.classList.remove('bg-primary');
                saveBtn.classList.add('bg-emerald-500');
                
                setTimeout(() => {
                    saveBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">save</span> 保存并下发';
                    saveBtn.classList.add('bg-primary');
                    saveBtn.classList.remove('bg-emerald-500');
                }, 2000);
            }, 600);
        });
    }

    // Bind Reset Button
    const resetBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('重置默认'));
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            if(confirm('确定要恢复默认策略参数吗？')) {
                localStorage.removeItem('quantA_strategy_params');
                location.reload();
            }
        });
    }
}, 100);
