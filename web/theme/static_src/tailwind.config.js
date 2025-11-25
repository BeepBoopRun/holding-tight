module.exports = {
	content: [
		// Templates within theme app (e.g. base.html)
		'../templates/**/*.html',
		// Templates in other apps
		'../../templates/**/*.html',
		// Ignore files in node_modules
		'!../../**/node_modules',
		'!../../user_uploads/',
		'!../../example_sims/',
		'!../../example_results/',
		// Include JavaScript files that might contain Tailwind CSS classes
		'../../**/*.js',
		// Include Python files that might contain Tailwind CSS classes
		'../../**/*.py'
	],
};
